<?php
/**
 * Siloq Cache Manager
 *
 * Manages caching of API responses to improve performance
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Cache_Manager {

    /**
     * Cache key prefix
     */
    const CACHE_PREFIX = 'siloq_cache_';

    /**
     * Default cache TTL (time to live) in seconds
     */
    const DEFAULT_TTL = 3600; // 1 hour

    /**
     * Cache TTL strategy by endpoint type
     */
    private $ttl_strategy = array(
        'gate_results' => 300,      // 5 minutes
        'page_metadata' => 600,     // 10 minutes
        'schema_data' => 900,       // 15 minutes
        'job_status' => 30,         // 30 seconds (during generation)
        'api_key_validation' => 1800, // 30 minutes
    );

    /**
     * Get cached data
     *
     * @param string $cache_key Cache key
     * @return mixed|false Cached data or false if not found/expired
     */
    public function get($cache_key) {
        $full_key = $this->get_full_key($cache_key);

        // Try transient first (faster for single requests)
        $cached = get_transient($full_key);

        if ($cached !== false) {
            return $cached;
        }

        // Try object cache (if available)
        if (function_exists('wp_cache_get')) {
            $cached = wp_cache_get($full_key, 'siloq');
            if ($cached !== false) {
                return $cached;
            }
        }

        return false;
    }

    /**
     * Set cached data
     *
     * @param string $cache_key Cache key
     * @param mixed $data Data to cache
     * @param int $ttl Time to live in seconds (optional)
     * @return bool True on success, false on failure
     */
    public function set($cache_key, $data, $ttl = null) {
        if ($ttl === null) {
            $ttl = self::DEFAULT_TTL;
        }

        $full_key = $this->get_full_key($cache_key);

        // Set transient
        $transient_result = set_transient($full_key, $data, $ttl);

        // Set object cache (if available)
        if (function_exists('wp_cache_set')) {
            wp_cache_set($full_key, $data, 'siloq', $ttl);
        }

        return $transient_result;
    }

    /**
     * Delete cached data
     *
     * @param string $cache_key Cache key
     * @return bool True on success, false on failure
     */
    public function delete($cache_key) {
        $full_key = $this->get_full_key($cache_key);

        // Delete transient
        $transient_result = delete_transient($full_key);

        // Delete from object cache (if available)
        if (function_exists('wp_cache_delete')) {
            wp_cache_delete($full_key, 'siloq');
        }

        return $transient_result;
    }

    /**
     * Clear all cached data
     *
     * @return int Number of cache entries cleared
     */
    public function clear_all() {
        global $wpdb;

        // Clear transients
        $sql = "DELETE FROM {$wpdb->options} WHERE option_name LIKE %s OR option_name LIKE %s";
        $deleted = $wpdb->query($wpdb->prepare(
            $sql,
            $wpdb->esc_like('_transient_' . self::CACHE_PREFIX) . '%',
            $wpdb->esc_like('_transient_timeout_' . self::CACHE_PREFIX) . '%'
        ));

        // Flush object cache group (if available)
        if (function_exists('wp_cache_flush_group')) {
            wp_cache_flush_group('siloq');
        }

        return intval($deleted / 2); // Divide by 2 because each transient has a timeout option
    }

    /**
     * Get cache key for API endpoint
     *
     * @param string $endpoint API endpoint
     * @param array $params Request parameters
     * @return string Cache key
     */
    public function get_cache_key($endpoint, $params = array()) {
        $key_parts = array($endpoint);

        if (!empty($params)) {
            ksort($params);
            $key_parts[] = md5(json_encode($params));
        }

        return implode('_', $key_parts);
    }

    /**
     * Get TTL for specific cache type
     *
     * @param string $cache_type Cache type
     * @return int TTL in seconds
     */
    public function get_ttl($cache_type) {
        return isset($this->ttl_strategy[$cache_type]) ? $this->ttl_strategy[$cache_type] : self::DEFAULT_TTL;
    }

    /**
     * Cache API response
     *
     * @param string $endpoint API endpoint
     * @param array $params Request parameters
     * @param mixed $response Response data
     * @param string $cache_type Cache type for TTL strategy
     * @return bool True on success
     */
    public function cache_api_response($endpoint, $params, $response, $cache_type = null) {
        $cache_key = $this->get_cache_key($endpoint, $params);
        $ttl = $cache_type ? $this->get_ttl($cache_type) : self::DEFAULT_TTL;

        return $this->set($cache_key, $response, $ttl);
    }

    /**
     * Get cached API response
     *
     * @param string $endpoint API endpoint
     * @param array $params Request parameters
     * @return mixed|false Cached response or false
     */
    public function get_cached_api_response($endpoint, $params = array()) {
        $cache_key = $this->get_cache_key($endpoint, $params);
        return $this->get($cache_key);
    }

    /**
     * Invalidate cache for specific entity
     *
     * @param string $entity_type Entity type (e.g., 'page', 'post')
     * @param int $entity_id Entity ID
     * @return int Number of cache entries invalidated
     */
    public function invalidate_entity_cache($entity_type, $entity_id) {
        global $wpdb;

        $pattern = self::CACHE_PREFIX . "{$entity_type}_{$entity_id}_%";

        $sql = "DELETE FROM {$wpdb->options} WHERE option_name LIKE %s OR option_name LIKE %s";
        $deleted = $wpdb->query($wpdb->prepare(
            $sql,
            $wpdb->esc_like('_transient_' . $pattern) . '%',
            $wpdb->esc_like('_transient_timeout_' . $pattern) . '%'
        ));

        return intval($deleted / 2);
    }

    /**
     * Get cache statistics
     *
     * @return array Cache statistics
     */
    public function get_cache_stats() {
        global $wpdb;

        // Count transients
        $total_transients = $wpdb->get_var($wpdb->prepare(
            "SELECT COUNT(*) FROM {$wpdb->options} WHERE option_name LIKE %s",
            $wpdb->esc_like('_transient_' . self::CACHE_PREFIX) . '%'
        ));

        // Calculate cache size (approximate)
        $cache_size_result = $wpdb->get_var($wpdb->prepare(
            "SELECT SUM(LENGTH(option_value)) FROM {$wpdb->options} WHERE option_name LIKE %s",
            $wpdb->esc_like('_transient_' . self::CACHE_PREFIX) . '%'
        ));

        $cache_size_kb = $cache_size_result ? round($cache_size_result / 1024, 2) : 0;

        // Get expired transients count
        $expired_transients = $wpdb->get_var($wpdb->prepare(
            "SELECT COUNT(*) FROM {$wpdb->options}
             WHERE option_name LIKE %s
             AND option_value < %d",
            $wpdb->esc_like('_transient_timeout_' . self::CACHE_PREFIX) . '%',
            time()
        ));

        return array(
            'total_entries' => intval($total_transients),
            'cache_size_kb' => $cache_size_kb,
            'expired_entries' => intval($expired_transients),
            'active_entries' => intval($total_transients) - intval($expired_transients),
        );
    }

    /**
     * Clean expired cache entries
     *
     * @return int Number of entries cleaned
     */
    public function clean_expired() {
        global $wpdb;

        // Get expired transient timeout keys
        $expired_keys = $wpdb->get_col($wpdb->prepare(
            "SELECT option_name FROM {$wpdb->options}
             WHERE option_name LIKE %s
             AND option_value < %d",
            $wpdb->esc_like('_transient_timeout_' . self::CACHE_PREFIX) . '%',
            time()
        ));

        $cleaned = 0;

        foreach ($expired_keys as $timeout_key) {
            // Extract the transient name
            $transient_key = str_replace('_transient_timeout_', '_transient_', $timeout_key);

            // Delete both the transient and its timeout
            $wpdb->query($wpdb->prepare(
                "DELETE FROM {$wpdb->options} WHERE option_name IN (%s, %s)",
                $transient_key,
                $timeout_key
            ));

            $cleaned++;
        }

        return $cleaned;
    }

    /**
     * Warm up cache for common queries
     *
     * @return array Results of cache warming
     */
    public function warm_up_cache() {
        $results = array(
            'warmed' => 0,
            'failed' => 0,
        );

        // This would typically pre-fetch commonly accessed data
        // For now, it's a placeholder for future implementation

        return $results;
    }

    /**
     * Get full cache key with prefix
     *
     * @param string $cache_key Base cache key
     * @return string Full cache key
     */
    private function get_full_key($cache_key) {
        return self::CACHE_PREFIX . $cache_key;
    }

    /**
     * Check if caching is enabled
     *
     * @return bool True if caching is enabled
     */
    public function is_caching_enabled() {
        return apply_filters('siloq_caching_enabled', true);
    }

    /**
     * Get or set cached data with callback
     *
     * @param string $cache_key Cache key
     * @param callable $callback Callback to generate data if not cached
     * @param int $ttl Time to live in seconds
     * @return mixed Cached or generated data
     */
    public function remember($cache_key, $callback, $ttl = null) {
        if (!$this->is_caching_enabled()) {
            return call_user_func($callback);
        }

        $cached = $this->get($cache_key);

        if ($cached !== false) {
            return $cached;
        }

        $data = call_user_func($callback);

        if ($data !== false && !is_wp_error($data)) {
            $this->set($cache_key, $data, $ttl);
        }

        return $data;
    }
}
