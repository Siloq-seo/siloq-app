<?php
/**
 * Siloq Cron Manager
 *
 * Manages scheduled background tasks for sync operations and maintenance
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Cron_Manager {

    /**
     * Register custom cron schedules
     *
     * @param array $schedules Existing schedules
     * @return array Modified schedules
     */
    public function add_cron_schedules($schedules) {
        // Every 5 minutes for queue processing
        $schedules['siloq_every_5_minutes'] = array(
            'interval' => 300,
            'display' => __('Every 5 Minutes (Siloq)', 'siloq-connector'),
        );

        // Every 15 minutes for pulling updates
        $schedules['siloq_every_15_minutes'] = array(
            'interval' => 900,
            'display' => __('Every 15 Minutes (Siloq)', 'siloq-connector'),
        );

        return $schedules;
    }

    /**
     * Schedule all cron jobs
     */
    public function schedule_jobs() {
        // Process sync queue every 5 minutes
        if (!wp_next_scheduled('siloq_process_queue')) {
            wp_schedule_event(time(), 'siloq_every_5_minutes', 'siloq_process_queue');
        }

        // Pull updates from Siloq every 15 minutes
        if (!wp_next_scheduled('siloq_pull_updates')) {
            wp_schedule_event(time(), 'siloq_every_15_minutes', 'siloq_pull_updates');
        }

        // Clear expired locks hourly
        if (!wp_next_scheduled('siloq_clear_locks')) {
            wp_schedule_event(time(), 'hourly', 'siloq_clear_locks');
        }

        // Cleanup old logs daily
        if (!wp_next_scheduled('siloq_cleanup_logs')) {
            wp_schedule_event(time(), 'daily', 'siloq_cleanup_logs');
        }
    }

    /**
     * Unschedule all cron jobs
     */
    public function unschedule_jobs() {
        $hooks = array(
            'siloq_process_queue',
            'siloq_pull_updates',
            'siloq_clear_locks',
            'siloq_cleanup_logs',
        );

        foreach ($hooks as $hook) {
            $timestamp = wp_next_scheduled($hook);
            if ($timestamp) {
                wp_unschedule_event($timestamp, $hook);
            }
        }
    }

    /**
     * Process sync queue
     * Runs every 5 minutes
     */
    public function process_sync_queue() {
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-sync-queue.php';

        $queue = new Siloq_Sync_Queue();

        // Check if queue processing is enabled
        if (!get_option('siloq_sync_enabled', true)) {
            return;
        }

        // Process up to 10 items per run
        $max_items = apply_filters('siloq_cron_max_queue_items', 10);
        $processed = 0;

        for ($i = 0; $i < $max_items; $i++) {
            $result = $queue->process_next();

            if ($result === false) {
                // Queue empty
                break;
            }

            $processed++;

            // Add small delay between processing
            if ($i < $max_items - 1) {
                usleep(100000); // 0.1 second
            }
        }

        if ($processed > 0) {
            error_log("Siloq Cron: Processed {$processed} queue items");
        }
    }

    /**
     * Pull updates from Siloq
     * Runs every 15 minutes
     */
    public function pull_updates_from_siloq() {
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-client.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-sync-engine.php';

        $api_client = new Siloq_API_Client();

        // Check if API is configured
        if (!$api_client->is_configured()) {
            return;
        }

        // Check if pull sync is enabled
        if (!get_option('siloq_pull_sync_enabled', false)) {
            return;
        }

        $sync_engine = new Siloq_Sync_Engine($api_client);

        // Get all posts that have Siloq mappings
        global $wpdb;
        $table = $wpdb->prefix . 'siloq_page_mappings';

        $mappings = $wpdb->get_results(
            "SELECT wp_post_id, siloq_page_id FROM {$table} LIMIT 50",
            ARRAY_A
        );

        if (empty($mappings)) {
            return;
        }

        $pulled = 0;
        $skipped = 0;

        foreach ($mappings as $mapping) {
            $wp_post_id = $mapping['wp_post_id'];
            $siloq_page_id = $mapping['siloq_page_id'];

            // Check if Siloq version is newer
            $conflict_status = $sync_engine->detect_conflict($wp_post_id, $siloq_page_id);

            if ($conflict_status === 'siloq_newer') {
                // Pull from Siloq
                $result = $sync_engine->pull_from_siloq($siloq_page_id);

                if (!is_wp_error($result)) {
                    $pulled++;
                } else {
                    error_log('Siloq Cron: Failed to pull ' . $siloq_page_id . ': ' . $result->get_error_message());
                }
            } else {
                $skipped++;
            }

            // Rate limiting
            usleep(200000); // 0.2 seconds between checks
        }

        if ($pulled > 0) {
            error_log("Siloq Cron: Pulled {$pulled} updates from Siloq (skipped {$skipped})");
        }
    }

    /**
     * Clear expired content locks
     * Runs hourly
     */
    public function clear_expired_locks() {
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-content-lock.php';

        $lock_manager = new Siloq_Content_Lock();
        $result = $lock_manager->clear_expired_locks();

        if ($result !== false && $result > 0) {
            error_log("Siloq Cron: Cleared {$result} expired locks");
        }
    }

    /**
     * Cleanup old logs and queue items
     * Runs daily
     */
    public function cleanup_old_logs() {
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-error-handler.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-sync-queue.php';

        $error_handler = new Siloq_Error_Handler();
        $queue = new Siloq_Sync_Queue();

        // Clear old errors (older than 30 days)
        $errors_deleted = $error_handler->clear_old_errors(30);

        // Clear old failed queue items (older than 7 days)
        $failed_deleted = $queue->cleanup_failed_items(7);

        // Clear old completed queue items (older than 30 days)
        $completed_deleted = $queue->cleanup_completed_items(30);

        error_log("Siloq Cron: Cleanup completed - Errors: {$errors_deleted}, Failed items: {$failed_deleted}, Completed items: {$completed_deleted}");
    }

    /**
     * Get cron status
     *
     * @return array Cron status information
     */
    public function get_cron_status() {
        $jobs = array(
            'siloq_process_queue' => array(
                'name' => __('Process Sync Queue', 'siloq-connector'),
                'schedule' => 'siloq_every_5_minutes',
                'next_run' => wp_next_scheduled('siloq_process_queue'),
            ),
            'siloq_pull_updates' => array(
                'name' => __('Pull Updates from Siloq', 'siloq-connector'),
                'schedule' => 'siloq_every_15_minutes',
                'next_run' => wp_next_scheduled('siloq_pull_updates'),
            ),
            'siloq_clear_locks' => array(
                'name' => __('Clear Expired Locks', 'siloq-connector'),
                'schedule' => 'hourly',
                'next_run' => wp_next_scheduled('siloq_clear_locks'),
            ),
            'siloq_cleanup_logs' => array(
                'name' => __('Cleanup Old Logs', 'siloq-connector'),
                'schedule' => 'daily',
                'next_run' => wp_next_scheduled('siloq_cleanup_logs'),
            ),
        );

        foreach ($jobs as $hook => &$job) {
            $job['is_scheduled'] = $job['next_run'] !== false;
            $job['next_run_formatted'] = $job['next_run'] ? date('Y-m-d H:i:s', $job['next_run']) : 'Not scheduled';
            $job['time_until'] = $job['next_run'] ? human_time_diff(time(), $job['next_run']) : 'N/A';
        }

        return $jobs;
    }

    /**
     * Manually trigger a cron job
     *
     * @param string $hook Cron hook name
     * @return bool|WP_Error True on success, error on failure
     */
    public function trigger_job_manually($hook) {
        $allowed_hooks = array(
            'siloq_process_queue',
            'siloq_pull_updates',
            'siloq_clear_locks',
            'siloq_cleanup_logs',
        );

        if (!in_array($hook, $allowed_hooks)) {
            return new WP_Error('invalid_hook', 'Invalid cron hook');
        }

        // Execute the hook
        do_action($hook);

        return true;
    }
}
