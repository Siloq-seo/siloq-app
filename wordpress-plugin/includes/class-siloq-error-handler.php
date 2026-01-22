<?php
/**
 * Siloq Error Handler
 *
 * Centralized error logging and notification system
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Error_Handler {

    /**
     * Option name for storing error notification settings
     */
    const NOTIFICATION_OPTION = 'siloq_error_notifications';

    /**
     * Log error to database
     *
     * @param string $error_code Error code
     * @param string $message Error message
     * @param array $context Additional context data
     * @return int|false Log entry ID or false on failure
     */
    public function log_error($error_code, $message, $context = array()) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_log';

        // Extract common fields from context
        $operation_type = isset($context['operation_type']) ? $context['operation_type'] : 'error';
        $entity_type = isset($context['entity_type']) ? $context['entity_type'] : 'system';
        $entity_id = isset($context['entity_id']) ? intval($context['entity_id']) : 0;
        $direction = isset($context['direction']) ? $context['direction'] : 'n/a';
        $queue_id = isset($context['queue_id']) ? intval($context['queue_id']) : null;
        $duration_ms = isset($context['duration_ms']) ? intval($context['duration_ms']) : null;

        // Prepare request and response payloads
        $request_payload = isset($context['request']) ? json_encode($context['request']) : null;
        $response_payload = isset($context['response']) ? json_encode($context['response']) : null;

        $data = array(
            'queue_id' => $queue_id,
            'operation_type' => $operation_type,
            'entity_type' => $entity_type,
            'entity_id' => $entity_id,
            'direction' => $direction,
            'status' => 'error',
            'request_payload' => $request_payload,
            'response_payload' => $response_payload,
            'error_message' => $error_code . ': ' . $message,
            'duration_ms' => $duration_ms,
            'created_at' => current_time('mysql'),
        );

        $result = $wpdb->insert($table, $data);

        if ($result === false) {
            // Fallback to error_log if database insert fails
            error_log('Siloq Error Handler: Failed to log error to database: ' . $wpdb->last_error);
            error_log('Siloq Error [' . $error_code . ']: ' . $message);
            return false;
        }

        $log_id = $wpdb->insert_id;

        // Check if admin notification should be sent
        if ($this->should_notify($error_code)) {
            $this->notify_admin(array(
                'error_code' => $error_code,
                'message' => $message,
                'context' => $context,
                'log_id' => $log_id,
            ));
        }

        // Also log to PHP error log for debugging
        error_log('Siloq Error [' . $error_code . ']: ' . $message . ' | Context: ' . json_encode($context));

        return $log_id;
    }

    /**
     * Get recent errors
     *
     * @param int $limit Number of errors to retrieve
     * @param string $entity_type Optional filter by entity type
     * @return array Array of error log entries
     */
    public function get_recent_errors($limit = 50, $entity_type = null) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_log';

        $where = "status = 'error'";
        if ($entity_type) {
            $where .= $wpdb->prepare(" AND entity_type = %s", $entity_type);
        }

        $sql = "SELECT * FROM {$table} WHERE {$where} ORDER BY created_at DESC LIMIT %d";

        return $wpdb->get_results($wpdb->prepare($sql, $limit), ARRAY_A);
    }

    /**
     * Clear old errors
     * Deletes errors older than the specified number of days
     *
     * @param int $days Number of days to keep (default: 30)
     * @return int|false Number of rows deleted or false on error
     */
    public function clear_old_errors($days = 30) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_log';

        $cutoff_date = date('Y-m-d H:i:s', strtotime("-{$days} days"));

        $result = $wpdb->query($wpdb->prepare(
            "DELETE FROM {$table} WHERE status = 'error' AND created_at < %s",
            $cutoff_date
        ));

        if ($result !== false) {
            error_log("Siloq Error Handler: Cleared {$result} old error logs");
        }

        return $result;
    }

    /**
     * Notify admin of error via email
     *
     * @param array $error Error data
     * @return bool True if notification sent, false otherwise
     */
    public function notify_admin($error) {
        // Check if notifications are enabled
        $notifications = get_option(self::NOTIFICATION_OPTION, array(
            'enabled' => false,
            'threshold' => 5, // Only notify after 5 errors
            'email' => get_option('admin_email'),
        ));

        if (!isset($notifications['enabled']) || !$notifications['enabled']) {
            return false;
        }

        // Get recent error count (last hour)
        $recent_error_count = $this->get_recent_error_count(60);

        // Only send notification if threshold is exceeded
        if ($recent_error_count < $notifications['threshold']) {
            return false;
        }

        $to = isset($notifications['email']) ? $notifications['email'] : get_option('admin_email');
        $subject = '[Siloq] Error Notification - ' . get_bloginfo('name');

        $message = "Siloq plugin has encountered an error:\n\n";
        $message .= "Error Code: " . $error['error_code'] . "\n";
        $message .= "Message: " . $error['message'] . "\n";
        $message .= "Time: " . current_time('mysql') . "\n\n";

        if (isset($error['context']) && !empty($error['context'])) {
            $message .= "Context:\n";
            $message .= print_r($error['context'], true) . "\n\n";
        }

        $message .= "Recent Error Count (last hour): {$recent_error_count}\n\n";
        $message .= "View logs: " . admin_url('admin.php?page=siloq-dashboard') . "\n";

        $headers = array('Content-Type: text/plain; charset=UTF-8');

        return wp_mail($to, $subject, $message, $headers);
    }

    /**
     * Format error for display
     *
     * @param array $error Error data
     * @return string Formatted error message
     */
    public function format_error($error) {
        if (is_wp_error($error)) {
            return $error->get_error_message();
        }

        if (is_array($error)) {
            $output = '';

            if (isset($error['error_message'])) {
                $output .= $error['error_message'];
            }

            if (isset($error['created_at'])) {
                $output .= ' (' . human_time_diff(strtotime($error['created_at'])) . ' ago)';
            }

            return $output;
        }

        return (string) $error;
    }

    /**
     * Check if admin should be notified for this error code
     *
     * @param string $error_code Error code
     * @return bool True if should notify
     */
    private function should_notify($error_code) {
        // Critical errors that should always notify
        $critical_errors = array(
            'api_error',
            'sync_failed',
            'database_error',
            'migration_failed',
        );

        return in_array($error_code, $critical_errors);
    }

    /**
     * Get recent error count
     *
     * @param int $minutes Number of minutes to look back
     * @return int Error count
     */
    private function get_recent_error_count($minutes = 60) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_log';

        $cutoff_time = date('Y-m-d H:i:s', strtotime("-{$minutes} minutes"));

        $count = $wpdb->get_var($wpdb->prepare(
            "SELECT COUNT(*) FROM {$table} WHERE status = 'error' AND created_at >= %s",
            $cutoff_time
        ));

        return intval($count);
    }

    /**
     * Get error statistics
     *
     * @return array Error statistics
     */
    public function get_error_stats() {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_log';

        // Total errors
        $total_errors = $wpdb->get_var("SELECT COUNT(*) FROM {$table} WHERE status = 'error'");

        // Errors in last 24 hours
        $yesterday = date('Y-m-d H:i:s', strtotime('-24 hours'));
        $errors_24h = $wpdb->get_var($wpdb->prepare(
            "SELECT COUNT(*) FROM {$table} WHERE status = 'error' AND created_at >= %s",
            $yesterday
        ));

        // Errors by type (last 7 days)
        $week_ago = date('Y-m-d H:i:s', strtotime('-7 days'));
        $errors_by_type = $wpdb->get_results($wpdb->prepare(
            "SELECT entity_type, COUNT(*) as count
             FROM {$table}
             WHERE status = 'error' AND created_at >= %s
             GROUP BY entity_type
             ORDER BY count DESC",
            $week_ago
        ), ARRAY_A);

        return array(
            'total_errors' => intval($total_errors),
            'errors_24h' => intval($errors_24h),
            'errors_by_type' => $errors_by_type,
        );
    }

    /**
     * Clear all errors for an entity
     *
     * @param string $entity_type Entity type
     * @param int $entity_id Entity ID
     * @return int|false Number of rows deleted or false on error
     */
    public function clear_entity_errors($entity_type, $entity_id) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_log';

        return $wpdb->delete(
            $table,
            array(
                'entity_type' => $entity_type,
                'entity_id' => $entity_id,
                'status' => 'error',
            ),
            array('%s', '%d', '%s')
        );
    }
}
