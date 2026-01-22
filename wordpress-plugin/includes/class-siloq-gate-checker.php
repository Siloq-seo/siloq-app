<?php
/**
 * Siloq Lifecycle Gate Checker
 *
 * Checks content against 10 lifecycle gates before publishing
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Gate_Checker {

    /**
     * API client instance
     */
    private $api_client;

    /**
     * 10 Lifecycle Gates
     */
    const GATES = array(
        'governance_checks' => 'Governance Checks Gate',
        'schema_sync' => 'Schema Sync Validation Gate',
        'embedding' => 'Embedding Gate',
        'authority' => 'Authority Gate',
        'content_structure' => 'Content Structure Gate',
        'status' => 'Status Gate',
        'experience_verification' => 'Experience Verification Gate (E-E-A-T)',
        'geo_formatting' => 'GEO Formatting Gate',
        'core_web_vitals' => 'Core Web Vitals Gate',
        'media_integrity' => 'Media Integrity Gate',
    );

    /**
     * Constructor
     */
    public function __construct($api_client = null) {
        $this->api_client = $api_client;

        if ($this->api_client === null) {
            require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-client.php';
            $this->api_client = new Siloq_API_Client();
        }
    }

    /**
     * Check all gates for a post
     *
     * @param int $wp_post_id WordPress post ID
     * @param bool $use_cache Whether to use cached results
     * @return array Gate results
     */
    public function check_all_gates($wp_post_id, $use_cache = true) {
        if (!$this->api_client || !$this->api_client->is_configured()) {
            return $this->get_error_results('API not configured');
        }

        // Check cache first
        if ($use_cache) {
            $cached = $this->get_cached_gate_results($wp_post_id);
            if ($cached !== false) {
                return $cached;
            }
        }

        // Get Siloq page ID
        $siloq_page_id = $this->api_client->get_siloq_page_id($wp_post_id);

        if (!$siloq_page_id) {
            return $this->get_error_results('No Siloq page mapping found');
        }

        // Call API to check gates
        $result = $this->api_client->check_publish_gates($siloq_page_id);

        if (is_wp_error($result)) {
            return $this->get_error_results($result->get_error_message());
        }

        // Parse and cache results
        $gate_results = $this->parse_gate_results($result, $wp_post_id, $siloq_page_id);

        // Cache results
        $this->cache_gate_results($wp_post_id, $siloq_page_id, $gate_results);

        return $gate_results;
    }

    /**
     * Check a single gate
     *
     * @param int $wp_post_id WordPress post ID
     * @param string $gate_name Gate name
     * @return array Gate result
     */
    public function check_gate($wp_post_id, $gate_name) {
        if (!isset(self::GATES[$gate_name])) {
            return array(
                'passed' => false,
                'error_code' => 'invalid_gate',
                'error_message' => 'Invalid gate name',
            );
        }

        $all_results = $this->check_all_gates($wp_post_id);

        return isset($all_results['gates'][$gate_name]) ? $all_results['gates'][$gate_name] : array(
            'passed' => false,
            'error_code' => 'gate_not_found',
            'error_message' => 'Gate result not found',
        );
    }

    /**
     * Get cached gate results
     *
     * @param int $wp_post_id WordPress post ID
     * @return array|false Cached results or false
     */
    public function get_cached_gate_results($wp_post_id) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_gate_results';

        // Get results cached within last 5 minutes
        $cutoff = date('Y-m-d H:i:s', strtotime('-5 minutes'));

        $results = $wpdb->get_results($wpdb->prepare(
            "SELECT * FROM {$table}
             WHERE wp_post_id = %d
             AND checked_at >= %s",
            $wp_post_id,
            $cutoff
        ), ARRAY_A);

        if (empty($results)) {
            return false;
        }

        // Build gate results array
        $gate_results = array(
            'all_passed' => true,
            'gates' => array(),
            'checked_at' => null,
        );

        foreach ($results as $row) {
            $gate_name = $row['gate_name'];
            $passed = (bool) $row['passed'];

            $gate_results['gates'][$gate_name] = array(
                'name' => isset(self::GATES[$gate_name]) ? self::GATES[$gate_name] : $gate_name,
                'passed' => $passed,
                'error_code' => $row['error_code'],
                'error_message' => $row['error_message'],
                'details' => !empty($row['details']) ? json_decode($row['details'], true) : array(),
            );

            if (!$passed) {
                $gate_results['all_passed'] = false;
            }

            if ($gate_results['checked_at'] === null || strtotime($row['checked_at']) > strtotime($gate_results['checked_at'])) {
                $gate_results['checked_at'] = $row['checked_at'];
            }
        }

        return $gate_results;
    }

    /**
     * Parse gate results from API response
     *
     * @param array $api_result API response
     * @param int $wp_post_id WordPress post ID
     * @param string $siloq_page_id Siloq page ID
     * @return array Parsed gate results
     */
    private function parse_gate_results($api_result, $wp_post_id, $siloq_page_id) {
        $gate_results = array(
            'all_passed' => isset($api_result['all_passed']) ? $api_result['all_passed'] : false,
            'gates' => array(),
            'checked_at' => current_time('mysql'),
        );

        $gates_data = isset($api_result['gates']) ? $api_result['gates'] : array();

        foreach (self::GATES as $gate_key => $gate_name) {
            $gate_data = isset($gates_data[$gate_key]) ? $gates_data[$gate_key] : null;

            if ($gate_data) {
                $gate_results['gates'][$gate_key] = array(
                    'name' => $gate_name,
                    'passed' => isset($gate_data['passed']) ? (bool) $gate_data['passed'] : false,
                    'error_code' => isset($gate_data['error_code']) ? $gate_data['error_code'] : null,
                    'error_message' => isset($gate_data['error_message']) ? $gate_data['error_message'] : null,
                    'details' => isset($gate_data['details']) ? $gate_data['details'] : array(),
                );
            } else {
                // Gate not returned by API
                $gate_results['gates'][$gate_key] = array(
                    'name' => $gate_name,
                    'passed' => false,
                    'error_code' => 'not_checked',
                    'error_message' => 'Gate not checked by API',
                    'details' => array(),
                );
            }
        }

        return $gate_results;
    }

    /**
     * Cache gate results to database
     *
     * @param int $wp_post_id WordPress post ID
     * @param string $siloq_page_id Siloq page ID
     * @param array $gate_results Gate results
     */
    private function cache_gate_results($wp_post_id, $siloq_page_id, $gate_results) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_gate_results';

        // Clear old results for this post
        $wpdb->delete($table, array('wp_post_id' => $wp_post_id), array('%d'));

        // Insert new results
        foreach ($gate_results['gates'] as $gate_key => $gate_data) {
            $wpdb->insert(
                $table,
                array(
                    'wp_post_id' => $wp_post_id,
                    'siloq_page_id' => $siloq_page_id,
                    'gate_name' => $gate_key,
                    'passed' => $gate_data['passed'] ? 1 : 0,
                    'error_code' => $gate_data['error_code'],
                    'error_message' => $gate_data['error_message'],
                    'details' => !empty($gate_data['details']) ? json_encode($gate_data['details']) : null,
                    'checked_at' => current_time('mysql'),
                ),
                array('%d', '%s', '%s', '%d', '%s', '%s', '%s', '%s')
            );
        }
    }

    /**
     * Get error results (when gate check fails)
     *
     * @param string $error_message Error message
     * @return array Error results
     */
    private function get_error_results($error_message) {
        $gate_results = array(
            'all_passed' => false,
            'gates' => array(),
            'error' => $error_message,
            'checked_at' => current_time('mysql'),
        );

        foreach (self::GATES as $gate_key => $gate_name) {
            $gate_results['gates'][$gate_key] = array(
                'name' => $gate_name,
                'passed' => false,
                'error_code' => 'check_failed',
                'error_message' => $error_message,
                'details' => array(),
            );
        }

        return $gate_results;
    }

    /**
     * Render gate results as HTML
     *
     * @param array $gate_results Gate results
     * @return string HTML output
     */
    public function render_gate_results($gate_results) {
        if (isset($gate_results['error'])) {
            return '<div class="notice notice-error"><p>' . esc_html($gate_results['error']) . '</p></div>';
        }

        $all_passed = isset($gate_results['all_passed']) ? $gate_results['all_passed'] : false;
        $checked_at = isset($gate_results['checked_at']) ? $gate_results['checked_at'] : '';

        ob_start();
        ?>
        <div class="siloq-gate-results">
            <div class="siloq-gate-summary">
                <?php if ($all_passed): ?>
                    <span class="dashicons dashicons-yes-alt" style="color: #46b450;"></span>
                    <strong><?php _e('All gates passed!', 'siloq-connector'); ?></strong>
                <?php else: ?>
                    <span class="dashicons dashicons-warning" style="color: #dc3232;"></span>
                    <strong><?php _e('Some gates failed', 'siloq-connector'); ?></strong>
                <?php endif; ?>
                <?php if ($checked_at): ?>
                    <span class="siloq-checked-time" style="margin-left: 10px; color: #646970; font-size: 12px;">
                        <?php printf(__('Checked: %s', 'siloq-connector'), human_time_diff(strtotime($checked_at)) . ' ago'); ?>
                    </span>
                <?php endif; ?>
            </div>

            <table class="widefat siloq-gates-table" style="margin-top: 10px;">
                <thead>
                    <tr>
                        <th style="width: 50px;"><?php _e('Status', 'siloq-connector'); ?></th>
                        <th><?php _e('Gate', 'siloq-connector'); ?></th>
                        <th><?php _e('Details', 'siloq-connector'); ?></th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($gate_results['gates'] as $gate_key => $gate_data): ?>
                        <tr>
                            <td style="text-align: center;">
                                <?php if ($gate_data['passed']): ?>
                                    <span class="dashicons dashicons-yes" style="color: #46b450;"></span>
                                <?php else: ?>
                                    <span class="dashicons dashicons-no" style="color: #dc3232;"></span>
                                <?php endif; ?>
                            </td>
                            <td><strong><?php echo esc_html($gate_data['name']); ?></strong></td>
                            <td>
                                <?php if (!$gate_data['passed'] && $gate_data['error_message']): ?>
                                    <span style="color: #dc3232;"><?php echo esc_html($gate_data['error_message']); ?></span>
                                <?php else: ?>
                                    <span style="color: #46b450;"><?php _e('Passed', 'siloq-connector'); ?></span>
                                <?php endif; ?>
                            </td>
                        </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        </div>
        <?php
        return ob_get_clean();
    }

    /**
     * Maybe block publish if gates fail
     * Hooked to pre_post_update
     *
     * @param int $post_id Post ID
     * @param array $data Post data
     */
    public function maybe_block_publish($post_id, $data) {
        // Only check when publishing
        if (!isset($data['post_status']) || $data['post_status'] !== 'publish') {
            return;
        }

        // Check if post is already published
        $post = get_post($post_id);
        if ($post && $post->post_status === 'publish') {
            // Already published, allow update
            return;
        }

        // Check if gate enforcement is enabled
        if (!get_option('siloq_enforce_gates', false)) {
            return;
        }

        // Check gates
        $gate_results = $this->check_all_gates($post_id, false);

        if (!$gate_results['all_passed']) {
            // Block publish
            wp_die(
                __('Cannot publish: Content failed lifecycle gate checks. Please review and fix issues in the Siloq metabox.', 'siloq-connector'),
                __('Publishing Blocked', 'siloq-connector'),
                array('back_link' => true)
            );
        }
    }

    /**
     * Clear cached gate results for a post
     *
     * @param int $wp_post_id WordPress post ID
     */
    public function clear_cache($wp_post_id) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_gate_results';

        $wpdb->delete($table, array('wp_post_id' => $wp_post_id), array('%d'));
    }
}
