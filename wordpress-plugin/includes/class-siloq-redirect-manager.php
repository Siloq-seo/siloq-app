<?php
/**
 * Siloq Redirect Manager
 * 
 * Manages redirects from Siloq governance decisions
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Redirect_Manager {
    
    /**
     * Apply redirect from Siloq
     */
    public function apply_redirect($source_url, $target_url, $redirect_type = 301) {
        global $wpdb;
        
        $table = $wpdb->prefix . 'siloq_redirects';
        
        // Check if redirect already exists
        $existing = $wpdb->get_var($wpdb->prepare(
            "SELECT id FROM {$table} WHERE source_url = %s",
            $source_url
        ));
        
        if ($existing) {
            // Update existing redirect
            $wpdb->update(
                $table,
                array(
                    'target_url' => $target_url,
                    'redirect_type' => intval($redirect_type),
                ),
                array('id' => $existing),
                array('%s', '%d'),
                array('%d')
            );
            
            return $existing;
        } else {
            // Insert new redirect
            $wpdb->insert(
                $table,
                array(
                    'source_url' => $source_url,
                    'target_url' => $target_url,
                    'redirect_type' => intval($redirect_type),
                    'created_at' => current_time('mysql'),
                ),
                array('%s', '%s', '%d', '%s')
            );
            
            return $wpdb->insert_id;
        }
    }
    
    /**
     * Get redirect for a URL
     */
    public function get_redirect($source_url) {
        global $wpdb;
        
        $table = $wpdb->prefix . 'siloq_redirects';
        
        // Try exact match first
        $redirect = $wpdb->get_row($wpdb->prepare(
            "SELECT target_url, redirect_type FROM {$table} WHERE source_url = %s LIMIT 1",
            $source_url
        ), ARRAY_A);
        
        if ($redirect) {
            return $redirect;
        }
        
        // Try path-only match (without query string)
        $path = strtok($source_url, '?');
        if ($path !== $source_url) {
            $redirect = $wpdb->get_row($wpdb->prepare(
                "SELECT target_url, redirect_type FROM {$table} WHERE source_url = %s LIMIT 1",
                $path
            ), ARRAY_A);
            
            if ($redirect) {
                return $redirect;
            }
        }
        
        return null;
    }
    
    /**
     * Remove redirect
     */
    public function remove_redirect($source_url) {
        global $wpdb;
        
        $table = $wpdb->prefix . 'siloq_redirects';
        
        return $wpdb->delete(
            $table,
            array('source_url' => $source_url),
            array('%s')
        );
    }
    
    /**
     * Get all redirects
     */
    public function get_all_redirects($limit = 100) {
        global $wpdb;
        
        $table = $wpdb->prefix . 'siloq_redirects';
        
        return $wpdb->get_results(
            $wpdb->prepare(
                "SELECT * FROM {$table} ORDER BY created_at DESC LIMIT %d",
                $limit
            ),
            ARRAY_A
        );
    }
    
    /**
     * Bulk import redirects from Siloq
     */
    public function import_redirects($redirects) {
        $imported = 0;
        $errors = array();
        
        foreach ($redirects as $redirect) {
            if (!isset($redirect['source_url']) || !isset($redirect['target_url'])) {
                $errors[] = 'Missing required fields: ' . json_encode($redirect);
                continue;
            }
            
            $result = $this->apply_redirect(
                $redirect['source_url'],
                $redirect['target_url'],
                isset($redirect['redirect_type']) ? $redirect['redirect_type'] : 301
            );
            
            if ($result) {
                $imported++;
            } else {
                $errors[] = 'Failed to import: ' . json_encode($redirect);
            }
        }
        
        return array(
            'imported' => $imported,
            'total' => count($redirects),
            'errors' => $errors,
        );
    }
    
    /**
     * Clear all redirects
     */
    public function clear_all_redirects() {
        global $wpdb;

        $table_name = $wpdb->prefix . 'siloq_redirects';

        // Use DELETE instead of TRUNCATE for better compatibility and proper escaping
        // TRUNCATE cannot be prepared in WordPress, so we use DELETE which is functionally similar
        return $wpdb->query(
            $wpdb->prepare("DELETE FROM %i", $table_name)
        );
    }
}

