<?php
/**
 * Siloq Schema Migration
 *
 * Handles database schema versioning and migrations
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Schema_Migration {

    /**
     * Option name for storing schema version
     */
    const VERSION_OPTION = 'siloq_schema_version';

    /**
     * Current schema version
     */
    const CURRENT_VERSION = '2.0.0';

    /**
     * Get current schema version
     *
     * @return string Current schema version
     */
    public function get_current_version() {
        return get_option(self::VERSION_OPTION, '1.0.0');
    }

    /**
     * Migrate to target version
     *
     * @param string $target_version Target schema version
     * @return bool|WP_Error True on success, error on failure
     */
    public function migrate($target_version = null) {
        if ($target_version === null) {
            $target_version = self::CURRENT_VERSION;
        }

        $current_version = $this->get_current_version();

        // Already at target version
        if (version_compare($current_version, $target_version, '>=')) {
            return true;
        }

        // Migrate to v2.0.0
        if (version_compare($current_version, '2.0.0', '<') && version_compare($target_version, '2.0.0', '>=')) {
            $result = $this->migrate_to_v2_0_0();
            if (is_wp_error($result)) {
                return $result;
            }
        }

        // Update version
        update_option(self::VERSION_OPTION, $target_version);

        return true;
    }

    /**
     * Migrate to version 2.0.0
     * Creates all new tables for production deployment
     *
     * @return bool|WP_Error True on success, error on failure
     */
    private function migrate_to_v2_0_0() {
        global $wpdb;

        require_once(ABSPATH . 'wp-admin/includes/upgrade.php');

        $charset_collate = $wpdb->get_charset_collate();
        $prefix = $wpdb->prefix;

        // Sync operation queue
        $table_sync_queue = $prefix . 'siloq_sync_queue';
        $sql_sync_queue = "CREATE TABLE {$table_sync_queue} (
            id bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
            operation_type varchar(50) NOT NULL,
            entity_type varchar(50) NOT NULL,
            entity_id bigint(20) UNSIGNED NOT NULL,
            direction varchar(20) NOT NULL,
            priority tinyint NOT NULL DEFAULT 5,
            status varchar(20) NOT NULL DEFAULT 'pending',
            retry_count int NOT NULL DEFAULT 0,
            max_retries int NOT NULL DEFAULT 3,
            error_message text,
            payload longtext,
            created_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            started_at datetime,
            completed_at datetime,
            PRIMARY KEY (id),
            KEY idx_status_priority (status, priority, created_at),
            KEY idx_entity (entity_type, entity_id)
        ) {$charset_collate};";

        // Sync audit log
        $table_sync_log = $prefix . 'siloq_sync_log';
        $sql_sync_log = "CREATE TABLE {$table_sync_log} (
            id bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
            queue_id bigint(20) UNSIGNED,
            operation_type varchar(50) NOT NULL,
            entity_type varchar(50) NOT NULL,
            entity_id bigint(20) UNSIGNED NOT NULL,
            direction varchar(20) NOT NULL,
            status varchar(20) NOT NULL,
            request_payload longtext,
            response_payload longtext,
            error_message text,
            duration_ms int,
            created_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_entity_time (entity_type, entity_id, created_at),
            KEY idx_queue (queue_id)
        ) {$charset_collate};";

        // Conflict prevention locks
        $table_locks = $prefix . 'siloq_content_locks';
        $sql_locks = "CREATE TABLE {$table_locks} (
            entity_type varchar(50) NOT NULL,
            entity_id bigint(20) UNSIGNED NOT NULL,
            locked_by varchar(50) NOT NULL,
            locked_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at datetime NOT NULL,
            lock_token varchar(64) NOT NULL,
            PRIMARY KEY (entity_type, entity_id),
            KEY idx_expires (expires_at)
        ) {$charset_collate};";

        // Lifecycle gate results cache
        $table_gates = $prefix . 'siloq_gate_results';
        $sql_gates = "CREATE TABLE {$table_gates} (
            wp_post_id bigint(20) UNSIGNED NOT NULL,
            siloq_page_id varchar(36) NOT NULL,
            gate_name varchar(50) NOT NULL,
            passed tinyint(1) NOT NULL,
            error_code varchar(50),
            error_message text,
            details longtext,
            checked_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (wp_post_id, gate_name),
            KEY idx_page (siloq_page_id),
            KEY idx_checked (checked_at)
        ) {$charset_collate};";

        // Generation job tracking
        $table_jobs = $prefix . 'siloq_job_status';
        $sql_jobs = "CREATE TABLE {$table_jobs} (
            wp_post_id bigint(20) UNSIGNED NOT NULL,
            siloq_job_id varchar(36) NOT NULL,
            siloq_page_id varchar(36),
            status varchar(50) NOT NULL,
            error_message text,
            progress_percentage tinyint NOT NULL DEFAULT 0,
            total_cost_usd decimal(10,4),
            created_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at datetime,
            PRIMARY KEY (wp_post_id),
            KEY idx_job (siloq_job_id),
            KEY idx_status (status)
        ) {$charset_collate};";

        // Execute migrations
        $results = array();
        $results['sync_queue'] = dbDelta($sql_sync_queue);
        $results['sync_log'] = dbDelta($sql_sync_log);
        $results['locks'] = dbDelta($sql_locks);
        $results['gates'] = dbDelta($sql_gates);
        $results['jobs'] = dbDelta($sql_jobs);

        // Check for errors
        if ($wpdb->last_error) {
            return new WP_Error('migration_failed', 'Database migration failed: ' . $wpdb->last_error, $results);
        }

        // Log migration
        error_log('Siloq schema migrated to v2.0.0');

        return true;
    }

    /**
     * Rollback to target version
     * WARNING: This will drop tables created in later versions
     *
     * @param string $target_version Target schema version
     * @return bool|WP_Error True on success, error on failure
     */
    public function rollback($target_version) {
        global $wpdb;

        $current_version = $this->get_current_version();

        // Already at or below target version
        if (version_compare($current_version, $target_version, '<=')) {
            return true;
        }

        // Rollback from v2.0.0 to v1.0.0
        if (version_compare($current_version, '2.0.0', '>=') && version_compare($target_version, '2.0.0', '<')) {
            $prefix = $wpdb->prefix;

            // Drop v2.0.0 tables
            $tables = array(
                $prefix . 'siloq_sync_queue',
                $prefix . 'siloq_sync_log',
                $prefix . 'siloq_content_locks',
                $prefix . 'siloq_gate_results',
                $prefix . 'siloq_job_status',
            );

            foreach ($tables as $table) {
                $wpdb->query("DROP TABLE IF EXISTS {$table}");
            }

            // Check for errors
            if ($wpdb->last_error) {
                return new WP_Error('rollback_failed', 'Database rollback failed: ' . $wpdb->last_error);
            }
        }

        // Update version
        update_option(self::VERSION_OPTION, $target_version);

        // Log rollback
        error_log("Siloq schema rolled back to {$target_version}");

        return true;
    }

    /**
     * Check if migration is needed
     *
     * @return bool True if migration is needed
     */
    public function is_migration_needed() {
        $current_version = $this->get_current_version();
        return version_compare($current_version, self::CURRENT_VERSION, '<');
    }

    /**
     * Get migration status for admin notice
     *
     * @return array Migration status data
     */
    public function get_migration_status() {
        $current_version = $this->get_current_version();
        $needs_migration = $this->is_migration_needed();

        return array(
            'current_version' => $current_version,
            'target_version' => self::CURRENT_VERSION,
            'needs_migration' => $needs_migration,
        );
    }

    /**
     * Verify all tables exist
     *
     * @return bool True if all tables exist
     */
    public function verify_tables() {
        global $wpdb;

        $prefix = $wpdb->prefix;
        $required_tables = array(
            $prefix . 'siloq_redirects',
            $prefix . 'siloq_page_mappings',
            $prefix . 'siloq_sync_queue',
            $prefix . 'siloq_sync_log',
            $prefix . 'siloq_content_locks',
            $prefix . 'siloq_gate_results',
            $prefix . 'siloq_job_status',
        );

        foreach ($required_tables as $table) {
            $result = $wpdb->get_var("SHOW TABLES LIKE '{$table}'");
            if ($result !== $table) {
                return false;
            }
        }

        return true;
    }
}
