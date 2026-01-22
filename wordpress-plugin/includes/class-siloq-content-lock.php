<?php
/**
 * Siloq Content Lock Manager
 *
 * Manages content locks to prevent sync conflicts during bidirectional operations
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Content_Lock {

    /**
     * Default lock duration in seconds
     */
    const DEFAULT_LOCK_DURATION = 1800; // 30 minutes

    /**
     * Acquire a lock for an entity
     *
     * @param string $entity_type Entity type (e.g., 'page', 'post')
     * @param int $entity_id Entity ID
     * @param string $source Source acquiring the lock (e.g., 'wordpress', 'siloq', 'queue_processor')
     * @param int $duration Lock duration in seconds
     * @return bool True if lock acquired, false if already locked
     */
    public function acquire_lock($entity_type, $entity_id, $source = 'wordpress', $duration = null) {
        global $wpdb;

        if ($duration === null) {
            $duration = self::DEFAULT_LOCK_DURATION;
        }

        $table = $wpdb->prefix . 'siloq_content_locks';

        // First, clean up any expired locks
        $this->clear_expired_locks();

        // Check if already locked
        if ($this->is_locked($entity_type, $entity_id)) {
            return false;
        }

        // Generate lock token
        $lock_token = $this->generate_lock_token($entity_type, $entity_id, $source);

        $expires_at = date('Y-m-d H:i:s', time() + $duration);

        $data = array(
            'entity_type' => $entity_type,
            'entity_id' => $entity_id,
            'locked_by' => $source,
            'locked_at' => current_time('mysql'),
            'expires_at' => $expires_at,
            'lock_token' => $lock_token,
        );

        $result = $wpdb->replace($table, $data);

        if ($result === false) {
            error_log('Siloq Content Lock: Failed to acquire lock - ' . $wpdb->last_error);
            return false;
        }

        return true;
    }

    /**
     * Release a lock for an entity
     *
     * @param string $entity_type Entity type
     * @param int $entity_id Entity ID
     * @return bool True if lock released, false otherwise
     */
    public function release_lock($entity_type, $entity_id) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_content_locks';

        $result = $wpdb->delete(
            $table,
            array(
                'entity_type' => $entity_type,
                'entity_id' => $entity_id,
            ),
            array('%s', '%d')
        );

        return $result !== false;
    }

    /**
     * Check if an entity is locked
     *
     * @param string $entity_type Entity type
     * @param int $entity_id Entity ID
     * @return bool True if locked, false otherwise
     */
    public function is_locked($entity_type, $entity_id) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_content_locks';

        $lock = $wpdb->get_row($wpdb->prepare(
            "SELECT * FROM {$table}
             WHERE entity_type = %s
             AND entity_id = %d
             AND expires_at > NOW()
             LIMIT 1",
            $entity_type,
            $entity_id
        ));

        return $lock !== null;
    }

    /**
     * Get lock information for an entity
     *
     * @param string $entity_type Entity type
     * @param int $entity_id Entity ID
     * @return array|null Lock information or null if not locked
     */
    public function get_lock_info($entity_type, $entity_id) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_content_locks';

        $lock = $wpdb->get_row($wpdb->prepare(
            "SELECT * FROM {$table}
             WHERE entity_type = %s
             AND entity_id = %d
             LIMIT 1",
            $entity_type,
            $entity_id
        ), ARRAY_A);

        if (!$lock) {
            return null;
        }

        // Check if expired
        if (strtotime($lock['expires_at']) < time()) {
            // Lock expired, remove it
            $this->release_lock($entity_type, $entity_id);
            return null;
        }

        return $lock;
    }

    /**
     * Clear all expired locks
     *
     * @return int|false Number of locks cleared or false on error
     */
    public function clear_expired_locks() {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_content_locks';

        $result = $wpdb->query(
            "DELETE FROM {$table} WHERE expires_at < NOW()"
        );

        if ($result !== false && $result > 0) {
            error_log("Siloq Content Lock: Cleared {$result} expired locks");
        }

        return $result;
    }

    /**
     * Extend an existing lock
     *
     * @param string $entity_type Entity type
     * @param int $entity_id Entity ID
     * @param int $additional_duration Additional duration in seconds
     * @return bool True if lock extended, false otherwise
     */
    public function extend_lock($entity_type, $entity_id, $additional_duration = 1800) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_content_locks';

        $lock = $this->get_lock_info($entity_type, $entity_id);

        if (!$lock) {
            return false;
        }

        $new_expires_at = date('Y-m-d H:i:s', strtotime($lock['expires_at']) + $additional_duration);

        $result = $wpdb->update(
            $table,
            array('expires_at' => $new_expires_at),
            array(
                'entity_type' => $entity_type,
                'entity_id' => $entity_id,
            ),
            array('%s'),
            array('%s', '%d')
        );

        return $result !== false;
    }

    /**
     * Get all active locks
     *
     * @param int $limit Number of locks to retrieve
     * @return array Active locks
     */
    public function get_active_locks($limit = 100) {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_content_locks';

        return $wpdb->get_results($wpdb->prepare(
            "SELECT * FROM {$table}
             WHERE expires_at > NOW()
             ORDER BY locked_at DESC
             LIMIT %d",
            $limit
        ), ARRAY_A);
    }

    /**
     * Force release a lock (use with caution)
     *
     * @param string $entity_type Entity type
     * @param int $entity_id Entity ID
     * @param string $reason Reason for force release
     * @return bool True if released, false otherwise
     */
    public function force_release_lock($entity_type, $entity_id, $reason = 'Manual intervention') {
        $lock_info = $this->get_lock_info($entity_type, $entity_id);

        if ($lock_info) {
            error_log("Siloq Content Lock: Force releasing lock for {$entity_type}:{$entity_id}. Reason: {$reason}. Previously locked by: {$lock_info['locked_by']}");
        }

        return $this->release_lock($entity_type, $entity_id);
    }

    /**
     * Generate a unique lock token
     *
     * @param string $entity_type Entity type
     * @param int $entity_id Entity ID
     * @param string $source Source
     * @return string Lock token
     */
    private function generate_lock_token($entity_type, $entity_id, $source) {
        return hash('sha256', $entity_type . ':' . $entity_id . ':' . $source . ':' . time() . ':' . wp_rand());
    }

    /**
     * Get lock statistics
     *
     * @return array Lock statistics
     */
    public function get_lock_stats() {
        global $wpdb;

        $table = $wpdb->prefix . 'siloq_content_locks';

        $active_locks = $wpdb->get_var("SELECT COUNT(*) FROM {$table} WHERE expires_at > NOW()");
        $expired_locks = $wpdb->get_var("SELECT COUNT(*) FROM {$table} WHERE expires_at <= NOW()");

        // Locks by source
        $locks_by_source = $wpdb->get_results(
            "SELECT locked_by, COUNT(*) as count
             FROM {$table}
             WHERE expires_at > NOW()
             GROUP BY locked_by",
            ARRAY_A
        );

        return array(
            'active_locks' => intval($active_locks),
            'expired_locks' => intval($expired_locks),
            'locks_by_source' => $locks_by_source,
        );
    }

    /**
     * Try to acquire lock with retry
     *
     * @param string $entity_type Entity type
     * @param int $entity_id Entity ID
     * @param string $source Source
     * @param int $max_attempts Maximum retry attempts
     * @param int $wait_ms Wait time between attempts in milliseconds
     * @return bool True if lock acquired, false otherwise
     */
    public function acquire_lock_with_retry($entity_type, $entity_id, $source = 'wordpress', $max_attempts = 3, $wait_ms = 1000) {
        for ($attempt = 1; $attempt <= $max_attempts; $attempt++) {
            if ($this->acquire_lock($entity_type, $entity_id, $source)) {
                return true;
            }

            if ($attempt < $max_attempts) {
                usleep($wait_ms * 1000);
            }
        }

        return false;
    }
}
