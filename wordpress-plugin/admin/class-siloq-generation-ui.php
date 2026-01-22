<?php
/**
 * Siloq Content Generation UI
 *
 * Handles UI for AI-powered content generation
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Generation_UI {

    /**
     * API client instance
     */
    private $api_client;

    /**
     * Constructor
     */
    public function __construct($api_client = null) {
        $this->api_client = $api_client;

        if ($this->api_client === null) {
            require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-client.php';
            $this->api_client = new Siloq_API_Client();
        }

        // Add metabox
        add_action('add_meta_boxes', array($this, 'add_generation_metabox'));

        // AJAX handlers
        add_action('wp_ajax_siloq_generate_content', array($this, 'ajax_generate_content'));
        add_action('wp_ajax_siloq_poll_job_status', array($this, 'ajax_poll_job_status'));
        add_action('wp_ajax_siloq_cancel_generation', array($this, 'ajax_cancel_generation'));
    }

    /**
     * Add generation metabox
     */
    public function add_generation_metabox() {
        $post_types = apply_filters('siloq_generation_post_types', array('page', 'post'));

        foreach ($post_types as $post_type) {
            add_meta_box(
                'siloq_generation',
                __('Siloq Content Generation', 'siloq-connector'),
                array($this, 'render_generation_metabox'),
                $post_type,
                'side',
                'default'
            );
        }
    }

    /**
     * Render generation metabox
     *
     * @param WP_Post $post Post object
     */
    public function render_generation_metabox($post) {
        if (!$this->api_client || !$this->api_client->is_configured()) {
            echo '<p>' . __('Siloq API is not configured.', 'siloq-connector') . '</p>';
            return;
        }

        $job_status = $this->get_current_job_status($post->ID);

        wp_nonce_field('siloq_generation_' . $post->ID, 'siloq_generation_nonce');

        ?>
        <div class="siloq-generation-ui" data-post-id="<?php echo esc_attr($post->ID); ?>">
            <?php if ($job_status): ?>
                <?php $this->render_job_status_display($job_status, $post->ID); ?>
            <?php else: ?>
                <?php $this->render_generation_controls($post); ?>
            <?php endif; ?>

            <div id="siloq-generation-message"></div>
        </div>

        <style>
            .siloq-generation-ui .siloq-job-status {
                padding: 10px;
                margin: 10px 0;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: #f9f9f9;
            }
            .siloq-generation-ui .siloq-progress-bar {
                width: 100%;
                height: 20px;
                background: #e0e0e0;
                border-radius: 4px;
                overflow: hidden;
                margin: 10px 0;
            }
            .siloq-generation-ui .siloq-progress-bar-fill {
                height: 100%;
                background: #0073aa;
                transition: width 0.3s ease;
            }
            .siloq-generation-ui .siloq-job-history {
                margin-top: 15px;
                font-size: 12px;
            }
            .siloq-generation-ui .siloq-job-history-item {
                padding: 5px;
                border-bottom: 1px solid #eee;
            }
        </style>
        <?php
    }

    /**
     * Render generation controls
     *
     * @param WP_Post $post Post object
     */
    private function render_generation_controls($post) {
        ?>
        <div class="siloq-generation-controls">
            <p>
                <button type="button" id="siloq-generate-content-btn" class="button button-primary" style="width: 100%;">
                    <?php _e('Generate Content', 'siloq-connector'); ?>
                </button>
            </p>

            <div class="siloq-generation-options">
                <p>
                    <label>
                        <input type="checkbox" id="siloq-gen-overwrite" value="1" />
                        <?php _e('Overwrite existing content', 'siloq-connector'); ?>
                    </label>
                </p>
            </div>

            <?php $this->render_job_history($post->ID); ?>
        </div>
        <?php
    }

    /**
     * Render job status display
     *
     * @param array $job_status Job status data
     * @param int $post_id Post ID
     */
    private function render_job_status_display($job_status, $post_id) {
        $status = $job_status['status'];
        $progress = isset($job_status['progress_percentage']) ? intval($job_status['progress_percentage']) : 0;

        ?>
        <div class="siloq-job-status" data-job-id="<?php echo esc_attr($job_status['siloq_job_id']); ?>">
            <p>
                <strong><?php _e('Generation Status:', 'siloq-connector'); ?></strong>
                <span class="siloq-status-badge"><?php echo esc_html(ucfirst($status)); ?></span>
            </p>

            <?php if (in_array($status, array('pending', 'processing'))): ?>
                <div class="siloq-progress-bar">
                    <div class="siloq-progress-bar-fill" style="width: <?php echo esc_attr($progress); ?>%;"></div>
                </div>
                <p style="text-align: center; font-size: 12px; color: #666;">
                    <?php echo esc_html($progress); ?>% complete
                </p>
            <?php endif; ?>

            <?php if ($status === 'failed' && !empty($job_status['error_message'])): ?>
                <p style="color: #dc3232;">
                    <strong><?php _e('Error:', 'siloq-connector'); ?></strong>
                    <?php echo esc_html($job_status['error_message']); ?>
                </p>
            <?php endif; ?>

            <?php if ($status === 'completed'): ?>
                <p style="color: #46b450;">
                    <span class="dashicons dashicons-yes-alt"></span>
                    <?php _e('Generation completed successfully!', 'siloq-connector'); ?>
                </p>
                <?php if (isset($job_status['total_cost_usd'])): ?>
                    <p style="font-size: 12px; color: #666;">
                        <?php printf(__('Cost: $%s USD', 'siloq-connector'), number_format($job_status['total_cost_usd'], 2)); ?>
                    </p>
                <?php endif; ?>
            <?php endif; ?>

            <p>
                <?php if (in_array($status, array('pending', 'processing'))): ?>
                    <button type="button" class="button siloq-cancel-generation-btn">
                        <?php _e('Cancel', 'siloq-connector'); ?>
                    </button>
                <?php endif; ?>
                <?php if (in_array($status, array('completed', 'failed'))): ?>
                    <button type="button" class="button siloq-clear-job-btn">
                        <?php _e('Clear', 'siloq-connector'); ?>
                    </button>
                <?php endif; ?>
            </p>
        </div>
        <?php
    }

    /**
     * Render job history
     *
     * @param int $post_id Post ID
     */
    private function render_job_history($post_id) {
        $history = get_post_meta($post_id, 'siloq_generation_history', true);

        if (empty($history) || !is_array($history)) {
            return;
        }

        // Show last 5 jobs
        $history = array_slice($history, -5);

        ?>
        <div class="siloq-job-history">
            <h4><?php _e('Recent Generations', 'siloq-connector'); ?></h4>
            <?php foreach (array_reverse($history) as $job): ?>
                <div class="siloq-job-history-item">
                    <strong><?php echo esc_html(ucfirst($job['status'])); ?></strong>
                    <span style="float: right;">
                        <?php echo esc_html(human_time_diff(strtotime($job['created_at']))); ?> ago
                    </span>
                    <?php if (isset($job['total_cost_usd'])): ?>
                        <br /><span style="color: #666;">$<?php echo number_format($job['total_cost_usd'], 2); ?></span>
                    <?php endif; ?>
                </div>
            <?php endforeach; ?>
        </div>
        <?php
    }

    /**
     * Get current job status for a post
     *
     * @param int $post_id Post ID
     * @return array|false Job status or false
     */
    private function get_current_job_status($post_id) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_job_status';

        $job = $wpdb->get_row($wpdb->prepare(
            "SELECT * FROM {$table} WHERE wp_post_id = %d",
            $post_id
        ), ARRAY_A);

        if (!$job) {
            return false;
        }

        // If job is pending or processing, check if it's still active
        if (in_array($job['status'], array('pending', 'processing'))) {
            // Check if job is older than 1 hour - might be stale
            if (strtotime($job['created_at']) < strtotime('-1 hour')) {
                // Poll API for actual status
                $api_status = $this->api_client->get_generation_job_status($job['siloq_job_id']);

                if (!is_wp_error($api_status) && isset($api_status['status'])) {
                    // Update local status
                    $this->update_job_status($post_id, $api_status);
                    return $api_status;
                }
            }
        }

        return $job;
    }

    /**
     * AJAX: Generate content
     */
    public function ajax_generate_content() {
        // Check permissions
        if (!current_user_can('edit_posts')) {
            wp_send_json_error(array('message' => __('Insufficient permissions', 'siloq-connector')));
            return;
        }

        $post_id = isset($_POST['post_id']) ? intval($_POST['post_id']) : 0;

        if (!$post_id) {
            wp_send_json_error(array('message' => __('Invalid post ID', 'siloq-connector')));
            return;
        }

        // Verify nonce
        if (!isset($_POST['nonce']) || !wp_verify_nonce($_POST['nonce'], 'siloq_generation_' . $post_id)) {
            wp_send_json_error(array('message' => __('Invalid nonce', 'siloq-connector')));
            return;
        }

        $overwrite = isset($_POST['overwrite']) && $_POST['overwrite'] === 'true';

        // Get Siloq page ID
        $siloq_page_id = $this->api_client->get_siloq_page_id($post_id);

        if (!$siloq_page_id) {
            wp_send_json_error(array('message' => __('No Siloq page mapping found', 'siloq-connector')));
            return;
        }

        // Trigger generation
        $result = $this->api_client->generate_content($siloq_page_id, array(
            'overwrite' => $overwrite,
        ));

        if (is_wp_error($result)) {
            wp_send_json_error(array('message' => $result->get_error_message()));
            return;
        }

        // Store job status
        $this->store_job_status($post_id, $result);

        wp_send_json_success(array(
            'message' => __('Content generation started', 'siloq-connector'),
            'job_id' => isset($result['job_id']) ? $result['job_id'] : null,
        ));
    }

    /**
     * AJAX: Poll job status
     */
    public function ajax_poll_job_status() {
        $post_id = isset($_POST['post_id']) ? intval($_POST['post_id']) : 0;

        if (!$post_id) {
            wp_send_json_error(array('message' => __('Invalid post ID', 'siloq-connector')));
            return;
        }

        $job_status = $this->get_current_job_status($post_id);

        if (!$job_status) {
            wp_send_json_error(array('message' => __('No job found', 'siloq-connector')));
            return;
        }

        // If job is active, poll API
        if (in_array($job_status['status'], array('pending', 'processing'))) {
            $api_status = $this->api_client->get_generation_job_status($job_status['siloq_job_id']);

            if (!is_wp_error($api_status)) {
                $this->update_job_status($post_id, $api_status);
                $job_status = $api_status;
            }
        }

        wp_send_json_success(array('job' => $job_status));
    }

    /**
     * AJAX: Cancel generation
     */
    public function ajax_cancel_generation() {
        $post_id = isset($_POST['post_id']) ? intval($_POST['post_id']) : 0;

        if (!$post_id) {
            wp_send_json_error(array('message' => __('Invalid post ID', 'siloq-connector')));
            return;
        }

        // Clear job status
        global $wpdb;
        $table = $wpdb->prefix . 'siloq_job_status';
        $wpdb->delete($table, array('wp_post_id' => $post_id), array('%d'));

        wp_send_json_success(array('message' => __('Generation cancelled', 'siloq-connector')));
    }

    /**
     * Store job status in database
     *
     * @param int $post_id Post ID
     * @param array $job_data Job data from API
     */
    private function store_job_status($post_id, $job_data) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_job_status';

        $wpdb->replace(
            $table,
            array(
                'wp_post_id' => $post_id,
                'siloq_job_id' => isset($job_data['job_id']) ? $job_data['job_id'] : '',
                'siloq_page_id' => isset($job_data['page_id']) ? $job_data['page_id'] : '',
                'status' => isset($job_data['status']) ? $job_data['status'] : 'pending',
                'progress_percentage' => isset($job_data['progress']) ? intval($job_data['progress']) : 0,
                'total_cost_usd' => isset($job_data['cost']) ? floatval($job_data['cost']) : null,
                'created_at' => current_time('mysql'),
            ),
            array('%d', '%s', '%s', '%s', '%d', '%f', '%s')
        );
    }

    /**
     * Update job status in database
     *
     * @param int $post_id Post ID
     * @param array $job_data Job data from API
     */
    private function update_job_status($post_id, $job_data) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_job_status';

        $update_data = array(
            'status' => isset($job_data['status']) ? $job_data['status'] : 'processing',
            'progress_percentage' => isset($job_data['progress']) ? intval($job_data['progress']) : 0,
        );

        if (isset($job_data['cost'])) {
            $update_data['total_cost_usd'] = floatval($job_data['cost']);
        }

        if (in_array($job_data['status'], array('completed', 'failed'))) {
            $update_data['completed_at'] = current_time('mysql');

            // Add to history
            $this->add_to_job_history($post_id, $job_data);
        }

        $wpdb->update(
            $table,
            $update_data,
            array('wp_post_id' => $post_id),
            array('%s', '%d', '%f', '%s'),
            array('%d')
        );
    }

    /**
     * Add job to history
     *
     * @param int $post_id Post ID
     * @param array $job_data Job data
     */
    private function add_to_job_history($post_id, $job_data) {
        $history = get_post_meta($post_id, 'siloq_generation_history', true);

        if (!is_array($history)) {
            $history = array();
        }

        $history[] = array(
            'job_id' => isset($job_data['job_id']) ? $job_data['job_id'] : '',
            'status' => isset($job_data['status']) ? $job_data['status'] : '',
            'total_cost_usd' => isset($job_data['cost']) ? floatval($job_data['cost']) : 0,
            'created_at' => current_time('mysql'),
        );

        // Keep last 20 jobs
        $history = array_slice($history, -20);

        update_post_meta($post_id, 'siloq_generation_history', $history);
    }
}
