<?php
/**
 * Siloq Post Metaboxes
 *
 * Registers and renders metaboxes on post edit screen
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Post_Metaboxes {

    /**
     * API client instance
     */
    private $api_client;

    /**
     * Gate checker instance
     */
    private $gate_checker;

    /**
     * Constructor
     */
    public function __construct() {
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-client.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-gate-checker.php';

        $this->api_client = new Siloq_API_Client();
        $this->gate_checker = new Siloq_Gate_Checker($this->api_client);

        add_action('add_meta_boxes', array($this, 'register_metaboxes'));
        add_action('admin_enqueue_scripts', array($this, 'enqueue_scripts'));

        // AJAX handlers
        add_action('wp_ajax_siloq_sync_now', array($this, 'ajax_sync_now'));
        add_action('wp_ajax_siloq_check_gates', array($this, 'ajax_check_gates'));
        add_action('wp_ajax_siloq_refresh_schema', array($this, 'ajax_refresh_schema'));
    }

    /**
     * Register all metaboxes
     */
    public function register_metaboxes() {
        $post_types = apply_filters('siloq_metabox_post_types', array('page', 'post'));

        foreach ($post_types as $post_type) {
            // Sync Status Metabox
            add_meta_box(
                'siloq_sync_status',
                __('Siloq Sync Status', 'siloq-connector'),
                array($this, 'render_sync_status_metabox'),
                $post_type,
                'side',
                'high'
            );

            // Lifecycle Gates Metabox
            add_meta_box(
                'siloq_gates',
                __('Lifecycle Gates', 'siloq-connector'),
                array($this, 'render_gate_check_metabox'),
                $post_type,
                'normal',
                'default'
            );

            // Schema Preview Metabox
            add_meta_box(
                'siloq_schema',
                __('Schema Preview', 'siloq-connector'),
                array($this, 'render_schema_preview_metabox'),
                $post_type,
                'normal',
                'low'
            );
        }
    }

    /**
     * Render sync status metabox
     *
     * @param WP_Post $post Post object
     */
    public function render_sync_status_metabox($post) {
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-sync-engine.php';

        $sync_engine = new Siloq_Sync_Engine($this->api_client);
        $sync_status = $sync_engine->get_sync_status($post->ID);

        $siloq_page_id = $sync_status['siloq_page_id'];
        $last_synced = $sync_status['last_synced'];
        $is_synced = $sync_status['is_synced'];

        // Check for conflicts
        $conflict_status = null;
        if ($siloq_page_id) {
            $conflict_status = $sync_engine->detect_conflict($post->ID, $siloq_page_id);
        }

        ?>
        <div class="siloq-sync-status-box" data-post-id="<?php echo esc_attr($post->ID); ?>">
            <?php if ($is_synced): ?>
                <p>
                    <span class="dashicons dashicons-yes-alt" style="color: #46b450;"></span>
                    <strong><?php _e('Synced', 'siloq-connector'); ?></strong>
                </p>

                <p>
                    <strong><?php _e('Siloq Page ID:', 'siloq-connector'); ?></strong><br />
                    <code style="font-size: 11px;"><?php echo esc_html($siloq_page_id); ?></code>
                    <?php if ($this->api_client->is_configured()): ?>
                        <br /><a href="<?php echo esc_url($this->get_siloq_page_url($siloq_page_id)); ?>" target="_blank">
                            <?php _e('View in Siloq', 'siloq-connector'); ?>
                        </a>
                    <?php endif; ?>
                </p>

                <?php if ($last_synced): ?>
                    <p>
                        <strong><?php _e('Last Synced:', 'siloq-connector'); ?></strong><br />
                        <?php echo esc_html(human_time_diff(strtotime($last_synced))); ?> ago
                    </p>
                <?php endif; ?>

                <?php if ($conflict_status === 'conflict'): ?>
                    <p style="color: #dc3232;">
                        <span class="dashicons dashicons-warning"></span>
                        <strong><?php _e('Conflict Detected!', 'siloq-connector'); ?></strong><br />
                        <?php _e('Both WordPress and Siloq have changes.', 'siloq-connector'); ?>
                    </p>
                <?php endif; ?>

            <?php else: ?>
                <p>
                    <span class="dashicons dashicons-warning" style="color: #f0b849;"></span>
                    <strong><?php _e('Not Synced', 'siloq-connector'); ?></strong>
                </p>
                <p><?php _e('This content has not been synced to Siloq yet.', 'siloq-connector'); ?></p>
            <?php endif; ?>

            <p>
                <button type="button" class="button button-primary siloq-sync-now-btn" style="width: 100%;">
                    <?php _e('Sync Now', 'siloq-connector'); ?>
                </button>
            </p>

            <div id="siloq-sync-message"></div>
        </div>
        <?php
    }

    /**
     * Render gate check metabox
     *
     * @param WP_Post $post Post object
     */
    public function render_gate_check_metabox($post) {
        if (!$this->api_client || !$this->api_client->is_configured()) {
            echo '<p>' . __('Siloq API is not configured.', 'siloq-connector') . '</p>';
            return;
        }

        $siloq_page_id = $this->api_client->get_siloq_page_id($post->ID);

        if (!$siloq_page_id) {
            echo '<p>' . __('Sync this post to Siloq first to check lifecycle gates.', 'siloq-connector') . '</p>';
            return;
        }

        // Get cached gate results
        $gate_results = $this->gate_checker->get_cached_gate_results($post->ID);

        ?>
        <div class="siloq-gates-box" data-post-id="<?php echo esc_attr($post->ID); ?>">
            <?php if ($gate_results): ?>
                <?php echo $this->gate_checker->render_gate_results($gate_results); ?>
            <?php else: ?>
                <p><?php _e('Gate checks have not been run yet.', 'siloq-connector'); ?></p>
            <?php endif; ?>

            <p style="margin-top: 15px;">
                <button type="button" class="button siloq-check-gates-btn">
                    <?php _e('Check Gates', 'siloq-connector'); ?>
                </button>

                <?php if ($gate_results && $gate_results['all_passed']): ?>
                    <button type="button" class="button button-primary siloq-publish-to-siloq-btn">
                        <?php _e('Publish to Siloq', 'siloq-connector'); ?>
                    </button>
                <?php endif; ?>
            </p>

            <div id="siloq-gates-message"></div>
        </div>
        <?php
    }

    /**
     * Render schema preview metabox
     *
     * @param WP_Post $post Post object
     */
    public function render_schema_preview_metabox($post) {
        $schema = get_post_meta($post->ID, 'siloq_jsonld_schema', true);

        if (is_string($schema)) {
            $schema = json_decode($schema, true);
        }

        ?>
        <div class="siloq-schema-box" data-post-id="<?php echo esc_attr($post->ID); ?>">
            <?php if (!empty($schema)): ?>
                <div class="siloq-schema-validation">
                    <span class="dashicons dashicons-yes-alt" style="color: #46b450;"></span>
                    <strong><?php _e('Schema Active', 'siloq-connector'); ?></strong>
                </div>

                <div class="siloq-schema-preview" style="margin-top: 10px;">
                    <pre style="background: #f5f5f5; padding: 10px; border: 1px solid #ddd; border-radius: 4px; max-height: 300px; overflow: auto; font-size: 11px;"><?php echo esc_html(json_encode($schema, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)); ?></pre>
                </div>

                <p style="margin-top: 10px;">
                    <button type="button" class="button siloq-copy-schema-btn">
                        <?php _e('Copy to Clipboard', 'siloq-connector'); ?>
                    </button>
                </p>
            <?php else: ?>
                <p><?php _e('No schema data available for this post.', 'siloq-connector'); ?></p>
            <?php endif; ?>

            <p style="margin-top: 10px;">
                <button type="button" class="button siloq-refresh-schema-btn">
                    <?php _e('Refresh Schema', 'siloq-connector'); ?>
                </button>
            </p>

            <div id="siloq-schema-message"></div>
        </div>
        <?php
    }

    /**
     * Enqueue scripts for metaboxes
     *
     * @param string $hook Current admin page hook
     */
    public function enqueue_scripts($hook) {
        if (!in_array($hook, array('post.php', 'post-new.php'))) {
            return;
        }

        wp_enqueue_script(
            'siloq-metaboxes',
            SILOQ_PLUGIN_URL . 'admin/js/metaboxes.js',
            array('jquery'),
            SILOQ_VERSION,
            true
        );

        wp_localize_script('siloq-metaboxes', 'siloqMetaboxes', array(
            'ajaxurl' => admin_url('admin-ajax.php'),
            'nonce' => wp_create_nonce('siloq_metabox_actions'),
        ));
    }

    /**
     * AJAX: Sync now
     */
    public function ajax_sync_now() {
        if (!current_user_can('edit_posts')) {
            wp_send_json_error(array('message' => __('Insufficient permissions', 'siloq-connector')));
            return;
        }

        $post_id = isset($_POST['post_id']) ? intval($_POST['post_id']) : 0;

        if (!$post_id) {
            wp_send_json_error(array('message' => __('Invalid post ID', 'siloq-connector')));
            return;
        }

        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-sync-engine.php';

        $sync_engine = new Siloq_Sync_Engine($this->api_client);
        $result = $sync_engine->sync_single_post($post_id);

        if (is_wp_error($result)) {
            wp_send_json_error(array('message' => $result->get_error_message()));
            return;
        }

        wp_send_json_success(array(
            'message' => __('Post synced successfully', 'siloq-connector'),
            'data' => $result,
        ));
    }

    /**
     * AJAX: Check gates
     */
    public function ajax_check_gates() {
        if (!current_user_can('edit_posts')) {
            wp_send_json_error(array('message' => __('Insufficient permissions', 'siloq-connector')));
            return;
        }

        $post_id = isset($_POST['post_id']) ? intval($_POST['post_id']) : 0;

        if (!$post_id) {
            wp_send_json_error(array('message' => __('Invalid post ID', 'siloq-connector')));
            return;
        }

        $gate_results = $this->gate_checker->check_all_gates($post_id, false);

        wp_send_json_success(array(
            'message' => __('Gates checked', 'siloq-connector'),
            'results' => $gate_results,
            'html' => $this->gate_checker->render_gate_results($gate_results),
        ));
    }

    /**
     * AJAX: Refresh schema
     */
    public function ajax_refresh_schema() {
        if (!current_user_can('edit_posts')) {
            wp_send_json_error(array('message' => __('Insufficient permissions', 'siloq-connector')));
            return;
        }

        $post_id = isset($_POST['post_id']) ? intval($_POST['post_id']) : 0;

        if (!$post_id) {
            wp_send_json_error(array('message' => __('Invalid post ID', 'siloq-connector')));
            return;
        }

        $siloq_page_id = $this->api_client->get_siloq_page_id($post_id);

        if (!$siloq_page_id) {
            wp_send_json_error(array('message' => __('No Siloq page mapping found', 'siloq-connector')));
            return;
        }

        $schema = $this->api_client->get_page_jsonld($siloq_page_id);

        if (is_wp_error($schema)) {
            wp_send_json_error(array('message' => $schema->get_error_message()));
            return;
        }

        update_post_meta($post_id, 'siloq_jsonld_schema', $schema);

        wp_send_json_success(array(
            'message' => __('Schema refreshed', 'siloq-connector'),
            'schema' => $schema,
        ));
    }

    /**
     * Get Siloq page URL
     *
     * @param string $siloq_page_id Siloq page ID
     * @return string URL
     */
    private function get_siloq_page_url($siloq_page_id) {
        $base_url = get_option('siloq_api_base_url', 'https://api.siloq.io/v1');
        $base_url = str_replace('/v1', '', $base_url);
        return $base_url . '/pages/' . $siloq_page_id;
    }
}
