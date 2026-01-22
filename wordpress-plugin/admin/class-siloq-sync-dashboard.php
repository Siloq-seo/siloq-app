<?php
/**
 * Siloq Sync Dashboard
 *
 * Central dashboard for monitoring and managing sync operations
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Sync_Dashboard {

    /**
     * Constructor
     */
    public function __construct() {
        add_action('admin_menu', array($this, 'add_dashboard_menu'));
        add_action('admin_enqueue_scripts', array($this, 'enqueue_dashboard_scripts'));

        // AJAX handlers
        add_action('wp_ajax_siloq_dashboard_stats', array($this, 'ajax_get_dashboard_stats'));
        add_action('wp_ajax_siloq_retry_operation', array($this, 'ajax_retry_operation'));
        add_action('wp_ajax_siloq_clear_queue', array($this, 'ajax_clear_queue'));
        add_action('wp_ajax_siloq_trigger_cron', array($this, 'ajax_trigger_cron'));
    }

    /**
     * Add dashboard menu
     */
    public function add_dashboard_menu() {
        add_menu_page(
            __('Siloq Dashboard', 'siloq-connector'),
            __('Siloq', 'siloq-connector'),
            'edit_posts',
            'siloq-dashboard',
            array($this, 'render_dashboard'),
            'dashicons-update',
            30
        );

        add_submenu_page(
            'siloq-dashboard',
            __('Dashboard', 'siloq-connector'),
            __('Dashboard', 'siloq-connector'),
            'edit_posts',
            'siloq-dashboard',
            array($this, 'render_dashboard')
        );
    }

    /**
     * Render dashboard page
     */
    public function render_dashboard() {
        if (!current_user_can('edit_posts')) {
            wp_die(__('You do not have sufficient permissions to access this page.'));
        }

        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-sync-queue.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-error-handler.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-cron-manager.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-content-lock.php';

        $queue = new Siloq_Sync_Queue();
        $error_handler = new Siloq_Error_Handler();
        $cron_manager = new Siloq_Cron_Manager();
        $lock_manager = new Siloq_Content_Lock();

        $queue_status = $queue->get_queue_status();
        $error_stats = $error_handler->get_error_stats();
        $cron_status = $cron_manager->get_cron_status();
        $lock_stats = $lock_manager->get_lock_stats();

        ?>
        <div class="wrap siloq-dashboard">
            <h1><?php echo esc_html(get_admin_page_title()); ?></h1>

            <!-- Quick Stats -->
            <div class="siloq-dashboard-stats">
                <?php $this->render_quick_stats($queue_status, $error_stats, $lock_stats); ?>
            </div>

            <!-- Tabs -->
            <h2 class="nav-tab-wrapper">
                <a href="#queue" class="nav-tab nav-tab-active"><?php _e('Sync Queue', 'siloq-connector'); ?></a>
                <a href="#activity" class="nav-tab"><?php _e('Recent Activity', 'siloq-connector'); ?></a>
                <a href="#errors" class="nav-tab"><?php _e('Errors', 'siloq-connector'); ?></a>
                <a href="#cron" class="nav-tab"><?php _e('Cron Jobs', 'siloq-connector'); ?></a>
                <a href="#locks" class="nav-tab"><?php _e('Content Locks', 'siloq-connector'); ?></a>
            </h2>

            <!-- Queue Tab -->
            <div id="queue" class="siloq-tab-content">
                <?php $this->render_queue_status($queue); ?>
            </div>

            <!-- Activity Tab -->
            <div id="activity" class="siloq-tab-content" style="display: none;">
                <?php $this->render_recent_activity(); ?>
            </div>

            <!-- Errors Tab -->
            <div id="errors" class="siloq-tab-content" style="display: none;">
                <?php $this->render_sync_errors($error_handler); ?>
            </div>

            <!-- Cron Tab -->
            <div id="cron" class="siloq-tab-content" style="display: none;">
                <?php $this->render_cron_status($cron_status); ?>
            </div>

            <!-- Locks Tab -->
            <div id="locks" class="siloq-tab-content" style="display: none;">
                <?php $this->render_locks_status($lock_manager, $lock_stats); ?>
            </div>

            <!-- Manual Actions -->
            <div class="siloq-manual-actions" style="margin-top: 30px;">
                <h2><?php _e('Manual Actions', 'siloq-connector'); ?></h2>
                <p>
                    <button type="button" class="button button-primary siloq-sync-all-btn">
                        <?php _e('Sync All Pages', 'siloq-connector'); ?>
                    </button>
                    <button type="button" class="button siloq-pull-all-btn">
                        <?php _e('Pull All Updates', 'siloq-connector'); ?>
                    </button>
                    <button type="button" class="button button-secondary siloq-clear-queue-btn">
                        <?php _e('Clear Completed Items', 'siloq-connector'); ?>
                    </button>
                </p>
            </div>
        </div>
        <?php
    }

    /**
     * Render quick stats
     */
    private function render_quick_stats($queue_status, $error_stats, $lock_stats) {
        $success_rate = $queue_status['completed'] > 0
            ? round(($queue_status['completed'] / ($queue_status['completed'] + $queue_status['failed'])) * 100, 1)
            : 0;

        ?>
        <div class="siloq-stats-grid">
            <div class="siloq-stat-card">
                <div class="siloq-stat-icon">
                    <span class="dashicons dashicons-upload"></span>
                </div>
                <div class="siloq-stat-content">
                    <h3><?php echo esc_html($queue_status['pending']); ?></h3>
                    <p><?php _e('Pending', 'siloq-connector'); ?></p>
                </div>
            </div>

            <div class="siloq-stat-card">
                <div class="siloq-stat-icon" style="background: #46b450;">
                    <span class="dashicons dashicons-yes-alt"></span>
                </div>
                <div class="siloq-stat-content">
                    <h3><?php echo esc_html($queue_status['completed']); ?></h3>
                    <p><?php _e('Completed', 'siloq-connector'); ?></p>
                </div>
            </div>

            <div class="siloq-stat-card">
                <div class="siloq-stat-icon" style="background: <?php echo $queue_status['failed'] > 0 ? '#dc3232' : '#46b450'; ?>;">
                    <span class="dashicons dashicons-no"></span>
                </div>
                <div class="siloq-stat-content">
                    <h3><?php echo esc_html($queue_status['failed']); ?></h3>
                    <p><?php _e('Failed', 'siloq-connector'); ?></p>
                </div>
            </div>

            <div class="siloq-stat-card">
                <div class="siloq-stat-icon" style="background: #00a0d2;">
                    <span class="dashicons dashicons-chart-line"></span>
                </div>
                <div class="siloq-stat-content">
                    <h3><?php echo esc_html($success_rate); ?>%</h3>
                    <p><?php _e('Success Rate', 'siloq-connector'); ?></p>
                </div>
            </div>

            <div class="siloq-stat-card">
                <div class="siloq-stat-icon" style="background: <?php echo $error_stats['errors_24h'] > 0 ? '#dc3232' : '#46b450'; ?>;">
                    <span class="dashicons dashicons-warning"></span>
                </div>
                <div class="siloq-stat-content">
                    <h3><?php echo esc_html($error_stats['errors_24h']); ?></h3>
                    <p><?php _e('Errors (24h)', 'siloq-connector'); ?></p>
                </div>
            </div>

            <div class="siloq-stat-card">
                <div class="siloq-stat-icon" style="background: <?php echo $lock_stats['active_locks'] > 0 ? '#f0b849' : '#46b450'; ?>;">
                    <span class="dashicons dashicons-lock"></span>
                </div>
                <div class="siloq-stat-content">
                    <h3><?php echo esc_html($lock_stats['active_locks']); ?></h3>
                    <p><?php _e('Active Locks', 'siloq-connector'); ?></p>
                </div>
            </div>
        </div>
        <?php
    }

    /**
     * Render queue status
     */
    private function render_queue_status($queue) {
        $items = $queue->get_recent_items(50);

        ?>
        <table class="wp-list-table widefat fixed striped">
            <thead>
                <tr>
                    <th><?php _e('ID', 'siloq-connector'); ?></th>
                    <th><?php _e('Operation', 'siloq-connector'); ?></th>
                    <th><?php _e('Entity', 'siloq-connector'); ?></th>
                    <th><?php _e('Direction', 'siloq-connector'); ?></th>
                    <th><?php _e('Status', 'siloq-connector'); ?></th>
                    <th><?php _e('Retries', 'siloq-connector'); ?></th>
                    <th><?php _e('Created', 'siloq-connector'); ?></th>
                    <th><?php _e('Actions', 'siloq-connector'); ?></th>
                </tr>
            </thead>
            <tbody>
                <?php if (empty($items)): ?>
                    <tr>
                        <td colspan="8"><?php _e('No items in queue', 'siloq-connector'); ?></td>
                    </tr>
                <?php else: ?>
                    <?php foreach ($items as $item): ?>
                        <tr>
                            <td><?php echo esc_html($item['id']); ?></td>
                            <td><?php echo esc_html($item['operation_type']); ?></td>
                            <td>
                                <a href="<?php echo esc_url(get_edit_post_link($item['entity_id'])); ?>">
                                    <?php echo esc_html(get_the_title($item['entity_id'])); ?>
                                </a>
                            </td>
                            <td><?php echo esc_html($item['direction']); ?></td>
                            <td>
                                <span class="siloq-status-badge siloq-status-<?php echo esc_attr($item['status']); ?>">
                                    <?php echo esc_html(ucfirst($item['status'])); ?>
                                </span>
                            </td>
                            <td><?php echo esc_html($item['retry_count']) . '/' . esc_html($item['max_retries']); ?></td>
                            <td><?php echo esc_html(human_time_diff(strtotime($item['created_at']))); ?> ago</td>
                            <td>
                                <?php if ($item['status'] === 'failed'): ?>
                                    <button type="button" class="button button-small siloq-retry-btn" data-queue-id="<?php echo esc_attr($item['id']); ?>">
                                        <?php _e('Retry', 'siloq-connector'); ?>
                                    </button>
                                <?php endif; ?>
                            </td>
                        </tr>
                    <?php endforeach; ?>
                <?php endif; ?>
            </tbody>
        </table>
        <?php
    }

    /**
     * Render recent activity
     */
    private function render_recent_activity() {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_log';
        $logs = $wpdb->get_results(
            "SELECT * FROM {$table} ORDER BY created_at DESC LIMIT 50",
            ARRAY_A
        );

        ?>
        <table class="wp-list-table widefat fixed striped">
            <thead>
                <tr>
                    <th><?php _e('Time', 'siloq-connector'); ?></th>
                    <th><?php _e('Operation', 'siloq-connector'); ?></th>
                    <th><?php _e('Entity', 'siloq-connector'); ?></th>
                    <th><?php _e('Direction', 'siloq-connector'); ?></th>
                    <th><?php _e('Status', 'siloq-connector'); ?></th>
                    <th><?php _e('Duration', 'siloq-connector'); ?></th>
                </tr>
            </thead>
            <tbody>
                <?php if (empty($logs)): ?>
                    <tr>
                        <td colspan="6"><?php _e('No activity yet', 'siloq-connector'); ?></td>
                    </tr>
                <?php else: ?>
                    <?php foreach ($logs as $log): ?>
                        <tr>
                            <td><?php echo esc_html(human_time_diff(strtotime($log['created_at']))); ?> ago</td>
                            <td><?php echo esc_html($log['operation_type']); ?></td>
                            <td>
                                <?php if ($log['entity_id']): ?>
                                    <a href="<?php echo esc_url(get_edit_post_link($log['entity_id'])); ?>">
                                        <?php echo esc_html(get_the_title($log['entity_id'])); ?>
                                    </a>
                                <?php else: ?>
                                    -
                                <?php endif; ?>
                            </td>
                            <td><?php echo esc_html($log['direction']); ?></td>
                            <td>
                                <span class="siloq-status-badge siloq-status-<?php echo esc_attr($log['status']); ?>">
                                    <?php echo esc_html(ucfirst($log['status'])); ?>
                                </span>
                            </td>
                            <td>
                                <?php if ($log['duration_ms']): ?>
                                    <?php echo esc_html($log['duration_ms']); ?>ms
                                <?php else: ?>
                                    -
                                <?php endif; ?>
                            </td>
                        </tr>
                    <?php endforeach; ?>
                <?php endif; ?>
            </tbody>
        </table>
        <?php
    }

    /**
     * Render sync errors
     */
    private function render_sync_errors($error_handler) {
        $errors = $error_handler->get_recent_errors(50);

        ?>
        <table class="wp-list-table widefat fixed striped">
            <thead>
                <tr>
                    <th><?php _e('Time', 'siloq-connector'); ?></th>
                    <th><?php _e('Operation', 'siloq-connector'); ?></th>
                    <th><?php _e('Entity', 'siloq-connector'); ?></th>
                    <th><?php _e('Error', 'siloq-connector'); ?></th>
                    <th><?php _e('Actions', 'siloq-connector'); ?></th>
                </tr>
            </thead>
            <tbody>
                <?php if (empty($errors)): ?>
                    <tr>
                        <td colspan="5"><?php _e('No errors', 'siloq-connector'); ?></td>
                    </tr>
                <?php else: ?>
                    <?php foreach ($errors as $error): ?>
                        <tr>
                            <td><?php echo esc_html(human_time_diff(strtotime($error['created_at']))); ?> ago</td>
                            <td><?php echo esc_html($error['operation_type']); ?></td>
                            <td>
                                <?php if ($error['entity_id']): ?>
                                    <a href="<?php echo esc_url(get_edit_post_link($error['entity_id'])); ?>">
                                        <?php echo esc_html(get_the_title($error['entity_id'])); ?>
                                    </a>
                                <?php else: ?>
                                    -
                                <?php endif; ?>
                            </td>
                            <td>
                                <span style="color: #dc3232;">
                                    <?php echo esc_html($error['error_message']); ?>
                                </span>
                            </td>
                            <td>
                                <?php if ($error['queue_id']): ?>
                                    <button type="button" class="button button-small siloq-retry-btn" data-queue-id="<?php echo esc_attr($error['queue_id']); ?>">
                                        <?php _e('Retry', 'siloq-connector'); ?>
                                    </button>
                                <?php endif; ?>
                            </td>
                        </tr>
                    <?php endforeach; ?>
                <?php endif; ?>
            </tbody>
        </table>
        <?php
    }

    /**
     * Render cron status
     */
    private function render_cron_status($cron_status) {
        ?>
        <table class="wp-list-table widefat fixed striped">
            <thead>
                <tr>
                    <th><?php _e('Job', 'siloq-connector'); ?></th>
                    <th><?php _e('Schedule', 'siloq-connector'); ?></th>
                    <th><?php _e('Status', 'siloq-connector'); ?></th>
                    <th><?php _e('Next Run', 'siloq-connector'); ?></th>
                    <th><?php _e('Actions', 'siloq-connector'); ?></th>
                </tr>
            </thead>
            <tbody>
                <?php foreach ($cron_status as $hook => $job): ?>
                    <tr>
                        <td><strong><?php echo esc_html($job['name']); ?></strong></td>
                        <td><?php echo esc_html($job['schedule']); ?></td>
                        <td>
                            <?php if ($job['is_scheduled']): ?>
                                <span class="dashicons dashicons-yes-alt" style="color: #46b450;"></span>
                                <?php _e('Scheduled', 'siloq-connector'); ?>
                            <?php else: ?>
                                <span class="dashicons dashicons-no" style="color: #dc3232;"></span>
                                <?php _e('Not Scheduled', 'siloq-connector'); ?>
                            <?php endif; ?>
                        </td>
                        <td><?php echo esc_html($job['next_run_formatted']); ?></td>
                        <td>
                            <button type="button" class="button button-small siloq-trigger-cron-btn" data-hook="<?php echo esc_attr($hook); ?>">
                                <?php _e('Run Now', 'siloq-connector'); ?>
                            </button>
                        </td>
                    </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
        <?php
    }

    /**
     * Render locks status
     */
    private function render_locks_status($lock_manager, $lock_stats) {
        $active_locks = $lock_manager->get_active_locks(100);

        ?>
        <div style="margin-bottom: 20px;">
            <h3><?php _e('Lock Statistics', 'siloq-connector'); ?></h3>
            <p>
                <strong><?php _e('Active Locks:', 'siloq-connector'); ?></strong> <?php echo esc_html($lock_stats['active_locks']); ?><br />
                <strong><?php _e('Expired Locks:', 'siloq-connector'); ?></strong> <?php echo esc_html($lock_stats['expired_locks']); ?>
            </p>
        </div>

        <table class="wp-list-table widefat fixed striped">
            <thead>
                <tr>
                    <th><?php _e('Entity', 'siloq-connector'); ?></th>
                    <th><?php _e('Locked By', 'siloq-connector'); ?></th>
                    <th><?php _e('Locked At', 'siloq-connector'); ?></th>
                    <th><?php _e('Expires At', 'siloq-connector'); ?></th>
                </tr>
            </thead>
            <tbody>
                <?php if (empty($active_locks)): ?>
                    <tr>
                        <td colspan="4"><?php _e('No active locks', 'siloq-connector'); ?></td>
                    </tr>
                <?php else: ?>
                    <?php foreach ($active_locks as $lock): ?>
                        <tr>
                            <td>
                                <?php if ($lock['entity_type'] === 'page'): ?>
                                    <a href="<?php echo esc_url(get_edit_post_link($lock['entity_id'])); ?>">
                                        <?php echo esc_html(get_the_title($lock['entity_id'])); ?>
                                    </a>
                                <?php else: ?>
                                    <?php echo esc_html($lock['entity_type']) . ':' . esc_html($lock['entity_id']); ?>
                                <?php endif; ?>
                            </td>
                            <td><?php echo esc_html($lock['locked_by']); ?></td>
                            <td><?php echo esc_html(human_time_diff(strtotime($lock['locked_at']))); ?> ago</td>
                            <td><?php echo esc_html(human_time_diff(time(), strtotime($lock['expires_at']))); ?></td>
                        </tr>
                    <?php endforeach; ?>
                <?php endif; ?>
            </tbody>
        </table>
        <?php
    }

    /**
     * Enqueue dashboard scripts
     */
    public function enqueue_dashboard_scripts($hook) {
        if ($hook !== 'toplevel_page_siloq-dashboard') {
            return;
        }

        wp_enqueue_script(
            'siloq-dashboard',
            SILOQ_PLUGIN_URL . 'admin/js/dashboard.js',
            array('jquery'),
            SILOQ_VERSION,
            true
        );

        wp_enqueue_style(
            'siloq-dashboard',
            SILOQ_PLUGIN_URL . 'admin/css/dashboard.css',
            array(),
            SILOQ_VERSION
        );

        wp_localize_script('siloq-dashboard', 'siloqDashboard', array(
            'ajaxurl' => admin_url('admin-ajax.php'),
            'nonce' => wp_create_nonce('siloq_dashboard'),
        ));
    }

    /**
     * AJAX: Get dashboard stats
     */
    public function ajax_get_dashboard_stats() {
        // Real-time stats update (for auto-refresh)
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-sync-queue.php';

        $queue = new Siloq_Sync_Queue();
        $status = $queue->get_queue_status();

        wp_send_json_success($status);
    }

    /**
     * AJAX: Retry operation
     */
    public function ajax_retry_operation() {
        if (!current_user_can('edit_posts')) {
            wp_send_json_error(array('message' => __('Insufficient permissions', 'siloq-connector')));
            return;
        }

        $queue_id = isset($_POST['queue_id']) ? intval($_POST['queue_id']) : 0;

        if (!$queue_id) {
            wp_send_json_error(array('message' => __('Invalid queue ID', 'siloq-connector')));
            return;
        }

        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-sync-queue.php';

        $queue = new Siloq_Sync_Queue();
        $result = $queue->retry_operation($queue_id);

        if ($result) {
            wp_send_json_success(array('message' => __('Operation queued for retry', 'siloq-connector')));
        } else {
            wp_send_json_error(array('message' => __('Failed to retry operation', 'siloq-connector')));
        }
    }

    /**
     * AJAX: Clear queue
     */
    public function ajax_clear_queue() {
        if (!current_user_can('manage_options')) {
            wp_send_json_error(array('message' => __('Insufficient permissions', 'siloq-connector')));
            return;
        }

        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-sync-queue.php';

        $queue = new Siloq_Sync_Queue();
        $deleted = $queue->cleanup_completed_items(0); // Delete all completed

        wp_send_json_success(array(
            'message' => sprintf(__('%d completed items cleared', 'siloq-connector'), $deleted),
        ));
    }

    /**
     * AJAX: Trigger cron job
     */
    public function ajax_trigger_cron() {
        if (!current_user_can('manage_options')) {
            wp_send_json_error(array('message' => __('Insufficient permissions', 'siloq-connector')));
            return;
        }

        $hook = isset($_POST['hook']) ? sanitize_text_field($_POST['hook']) : '';

        if (!$hook) {
            wp_send_json_error(array('message' => __('Invalid hook', 'siloq-connector')));
            return;
        }

        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-cron-manager.php';

        $cron_manager = new Siloq_Cron_Manager();
        $result = $cron_manager->trigger_job_manually($hook);

        if (is_wp_error($result)) {
            wp_send_json_error(array('message' => $result->get_error_message()));
        } else {
            wp_send_json_success(array('message' => __('Cron job executed', 'siloq-connector')));
        }
    }
}
