<?php
/**
 * Siloq Sync Queue Manager
 *
 * Manages the queue of sync operations for bidirectional content sync
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Sync_Queue {

    /**
     * Enqueue a sync operation
     *
     * @param string $operation_type Operation type (sync_to_siloq, sync_from_siloq, delete, publish)
     * @param int $entity_id Entity ID (WordPress post ID)
     * @param string $direction Direction (push, pull)
     * @param int $priority Priority (1-10, lower = higher priority)
     * @param array $payload Additional payload data
     * @return int|false Queue ID or false on failure
     */
    public function enqueue($operation_type, $entity_id, $direction = 'push', $priority = 5, $payload = array()) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_queue';

        // Check if operation already queued for this entity
        $existing = $wpdb->get_row($wpdb->prepare(
            "SELECT id FROM {$table}
             WHERE entity_type = 'page'
             AND entity_id = %d
             AND status IN ('pending', 'processing')
             AND operation_type = %s
             LIMIT 1",
            $entity_id,
            $operation_type
        ));

        if ($existing) {
            // Already queued, return existing ID
            return $existing->id;
        }

        $data = array(
            'operation_type' => $operation_type,
            'entity_type' => 'page',
            'entity_id' => $entity_id,
            'direction' => $direction,
            'priority' => $priority,
            'status' => 'pending',
            'retry_count' => 0,
            'max_retries' => 3,
            'payload' => !empty($payload) ? json_encode($payload) : null,
            'created_at' => current_time('mysql'),
        );

        $result = $wpdb->insert($table, $data);

        if ($result === false) {
            error_log('Siloq Sync Queue: Failed to enqueue operation - ' . $wpdb->last_error);
            return false;
        }

        return $wpdb->insert_id;
    }

    /**
     * Process next item in queue
     *
     * @return array|false Result of processing or false if queue is empty
     */
    public function process_next() {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_queue';

        // Get highest priority pending item
        $item = $wpdb->get_row(
            "SELECT * FROM {$table}
             WHERE status = 'pending'
             ORDER BY priority ASC, created_at ASC
             LIMIT 1",
            ARRAY_A
        );

        if (!$item) {
            return false;
        }

        // Mark as processing
        $wpdb->update(
            $table,
            array(
                'status' => 'processing',
                'started_at' => current_time('mysql'),
            ),
            array('id' => $item['id']),
            array('%s', '%s'),
            array('%d')
        );

        // Process the item
        $result = $this->process_item($item);

        // Update queue item status
        if (is_wp_error($result)) {
            $this->handle_failure($item, $result);
        } else {
            $this->handle_success($item, $result);
        }

        return $result;
    }

    /**
     * Process a queue item
     *
     * @param array $item Queue item
     * @return array|WP_Error Result or error
     */
    private function process_item($item) {
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-client.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-sync-engine.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-content-lock.php';

        $api_client = new Siloq_API_Client();
        $sync_engine = new Siloq_Sync_Engine($api_client);
        $lock_manager = new Siloq_Content_Lock();

        $entity_id = $item['entity_id'];
        $payload = !empty($item['payload']) ? json_decode($item['payload'], true) : array();

        // Try to acquire lock
        if (!$lock_manager->acquire_lock('page', $entity_id, 'queue_processor')) {
            return new WP_Error('locked', 'Content is locked by another process');
        }

        $start_time = microtime(true);
        $result = null;

        try {
            switch ($item['operation_type']) {
                case 'sync_to_siloq':
                    $result = $sync_engine->sync_single_post($entity_id);
                    break;

                case 'sync_from_siloq':
                    $siloq_page_id = isset($payload['siloq_page_id']) ? $payload['siloq_page_id'] : null;
                    if (!$siloq_page_id) {
                        $siloq_page_id = $api_client->get_siloq_page_id($entity_id);
                    }
                    if ($siloq_page_id) {
                        $result = $sync_engine->pull_from_siloq($siloq_page_id);
                    } else {
                        $result = new WP_Error('no_mapping', 'No Siloq page ID found for this post');
                    }
                    break;

                case 'delete':
                    // Handle delete operation
                    $result = array('success' => true, 'message' => 'Delete operation not implemented yet');
                    break;

                case 'publish':
                    // Handle publish with gate checks
                    $result = array('success' => true, 'message' => 'Publish operation not implemented yet');
                    break;

                default:
                    $result = new WP_Error('unknown_operation', 'Unknown operation type: ' . $item['operation_type']);
                    break;
            }
        } finally {
            // Always release lock
            $lock_manager->release_lock('page', $entity_id);
        }

        $duration_ms = round((microtime(true) - $start_time) * 1000);

        // Log the operation
        $this->log_operation($item, $result, $duration_ms);

        return $result;
    }

    /**
     * Handle successful operation
     *
     * @param array $item Queue item
     * @param array $result Result data
     */
    private function handle_success($item, $result) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_queue';

        $wpdb->update(
            $table,
            array(
                'status' => 'completed',
                'completed_at' => current_time('mysql'),
            ),
            array('id' => $item['id']),
            array('%s', '%s'),
            array('%d')
        );
    }

    /**
     * Handle failed operation
     *
     * @param array $item Queue item
     * @param WP_Error $error Error object
     */
    private function handle_failure($item, $error) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_queue';

        $retry_count = intval($item['retry_count']) + 1;
        $max_retries = intval($item['max_retries']);

        if ($retry_count < $max_retries) {
            // Retry later
            $wpdb->update(
                $table,
                array(
                    'status' => 'pending',
                    'retry_count' => $retry_count,
                    'error_message' => $error->get_error_message(),
                ),
                array('id' => $item['id']),
                array('%s', '%d', '%s'),
                array('%d')
            );
        } else {
            // Max retries exceeded, mark as failed
            $wpdb->update(
                $table,
                array(
                    'status' => 'failed',
                    'error_message' => $error->get_error_message(),
                    'completed_at' => current_time('mysql'),
                ),
                array('id' => $item['id']),
                array('%s', '%s', '%s'),
                array('%d')
            );
        }
    }

    /**
     * Log sync operation to audit log
     *
     * @param array $item Queue item
     * @param array|WP_Error $result Result data or error
     * @param int $duration_ms Duration in milliseconds
     */
    private function log_operation($item, $result, $duration_ms) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_log';

        $payload = !empty($item['payload']) ? json_decode($item['payload'], true) : array();

        $data = array(
            'queue_id' => $item['id'],
            'operation_type' => $item['operation_type'],
            'entity_type' => $item['entity_type'],
            'entity_id' => $item['entity_id'],
            'direction' => $item['direction'],
            'status' => is_wp_error($result) ? 'error' : 'success',
            'request_payload' => !empty($payload) ? json_encode($payload) : null,
            'response_payload' => !is_wp_error($result) ? json_encode($result) : null,
            'error_message' => is_wp_error($result) ? $result->get_error_message() : null,
            'duration_ms' => $duration_ms,
            'created_at' => current_time('mysql'),
        );

        $wpdb->insert($table, $data);
    }

    /**
     * Get queue status
     *
     * @return array Queue statistics
     */
    public function get_queue_status() {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_queue';

        $pending = $wpdb->get_var("SELECT COUNT(*) FROM {$table} WHERE status = 'pending'");
        $processing = $wpdb->get_var("SELECT COUNT(*) FROM {$table} WHERE status = 'processing'");
        $completed = $wpdb->get_var("SELECT COUNT(*) FROM {$table} WHERE status = 'completed'");
        $failed = $wpdb->get_var("SELECT COUNT(*) FROM {$table} WHERE status = 'failed'");

        return array(
            'pending' => intval($pending),
            'processing' => intval($processing),
            'completed' => intval($completed),
            'failed' => intval($failed),
            'total' => intval($pending) + intval($processing) + intval($completed) + intval($failed),
        );
    }

    /**
     * Clean up failed items that exceeded max retries
     *
     * @param int $days Delete failed items older than this many days
     * @return int|false Number of items deleted
     */
    public function cleanup_failed_items($days = 7) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_queue';

        $cutoff_date = date('Y-m-d H:i:s', strtotime("-{$days} days"));

        return $wpdb->query($wpdb->prepare(
            "DELETE FROM {$table} WHERE status = 'failed' AND completed_at < %s",
            $cutoff_date
        ));
    }

    /**
     * Retry a specific queue item
     *
     * @param int $queue_id Queue item ID
     * @return bool True on success
     */
    public function retry_operation($queue_id) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_queue';

        return $wpdb->update(
            $table,
            array(
                'status' => 'pending',
                'retry_count' => 0,
                'error_message' => null,
            ),
            array('id' => $queue_id),
            array('%s', '%d', '%s'),
            array('%d')
        ) !== false;
    }

    /**
     * Get recent queue items
     *
     * @param int $limit Number of items to retrieve
     * @param string $status Optional status filter
     * @return array Queue items
     */
    public function get_recent_items($limit = 50, $status = null) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_queue';

        if ($status) {
            $sql = $wpdb->prepare(
                "SELECT * FROM {$table} WHERE status = %s ORDER BY created_at DESC LIMIT %d",
                $status,
                $limit
            );
        } else {
            $sql = $wpdb->prepare(
                "SELECT * FROM {$table} ORDER BY created_at DESC LIMIT %d",
                $limit
            );
        }

        return $wpdb->get_results($sql, ARRAY_A);
    }

    /**
     * Clear completed items older than specified days
     *
     * @param int $days Delete completed items older than this many days
     * @return int|false Number of items deleted
     */
    public function cleanup_completed_items($days = 30) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_sync_queue';

        $cutoff_date = date('Y-m-d H:i:s', strtotime("-{$days} days"));

        return $wpdb->query($wpdb->prepare(
            "DELETE FROM {$table} WHERE status = 'completed' AND completed_at < %s",
            $cutoff_date
        ));
    }
}
