<?php
/**
 * Siloq Sync Engine
 * 
 * Handles bidirectional content synchronization between WordPress and Siloq
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Sync_Engine {
    
    /**
     * API client instance
     */
    private $api_client;
    
    /**
     * Constructor
     */
    public function __construct($api_client) {
        $this->api_client = $api_client;
    }
    
    /**
     * Sync WordPress pages to Siloq (one-way)
     */
    public function sync_to_siloq($post_type = 'page', $limit = 100) {
        $posts = get_posts(array(
            'post_type' => $post_type,
            'post_status' => 'publish',
            'posts_per_page' => $limit,
            'orderby' => 'date',
            'order' => 'DESC',
        ));
        
        $synced = 0;
        $errors = array();
        
        foreach ($posts as $post) {
            $result = $this->sync_single_post($post->ID);
            
            if (is_wp_error($result)) {
                $errors[] = array(
                    'post_id' => $post->ID,
                    'title' => $post->post_title,
                    'error' => $result->get_error_message(),
                );
            } else {
                $synced++;
            }
            
            // Rate limiting - sleep briefly between requests
            usleep(500000); // 0.5 seconds
        }
        
        return array(
            'synced' => $synced,
            'total' => count($posts),
            'errors' => $errors,
        );
    }
    
    /**
     * Sync single post to Siloq
     */
    public function sync_single_post($wp_post_id) {
        if (!$this->api_client || !$this->api_client->is_configured()) {
            return new WP_Error('not_configured', 'Siloq API is not configured');
        }
        
        $post = get_post($wp_post_id);
        if (!$post) {
            return new WP_Error('invalid_post', 'Post not found');
        }
        
        // Skip non-published posts
        if ($post->post_status !== 'publish') {
            return new WP_Error('not_published', 'Post is not published');
        }
        
        // Check if already mapped
        $siloq_page_id = $this->api_client->get_siloq_page_id($wp_post_id);
        
        if ($siloq_page_id) {
            // Update existing page
            $result = $this->api_client->update_page($wp_post_id, $siloq_page_id);
        } else {
            // Create new page
            $result = $this->api_client->create_page($wp_post_id);
        }
        
        if (is_wp_error($result)) {
            error_log('Siloq sync error for post ' . $wp_post_id . ': ' . $result->get_error_message());
            return $result;
        }
        
        // Store sync metadata
        update_post_meta($wp_post_id, 'siloq_last_synced', current_time('mysql'));
        update_post_meta($wp_post_id, 'siloq_sync_status', 'success');
        
        return $result;
    }
    
    /**
     * Receive content from Siloq and apply to WordPress
     */
    public function receive_from_siloq($payload) {
        // Validate payload
        if (!isset($payload['wp_post_id']) || !isset($payload['html_content'])) {
            return new WP_Error('invalid_payload', 'Missing required fields in payload');
        }
        
        $wp_post_id = intval($payload['wp_post_id']);
        $post = get_post($wp_post_id);
        
        if (!$post) {
            return new WP_Error('post_not_found', 'WordPress post not found');
        }
        
        // Update post content
        $updated = wp_update_post(array(
            'ID' => $wp_post_id,
            'post_content' => wp_kses_post($payload['html_content']),
        ));
        
        if (is_wp_error($updated)) {
            return $updated;
        }
        
        // Update FAQs if provided
        if (isset($payload['faq_items']) && is_array($payload['faq_items'])) {
            update_post_meta($wp_post_id, 'siloq_faq_items', $payload['faq_items']);
            
            // Generate FAQ schema
            $this->update_faq_schema($wp_post_id, $payload['faq_items']);
        }
        
        // Update JSON-LD schema if provided
        if (isset($payload['jsonld_schema'])) {
            update_post_meta($wp_post_id, 'siloq_jsonld_schema', $payload['jsonld_schema']);
        }
        
        // Update internal links if provided
        if (isset($payload['internal_links']) && is_array($payload['internal_links'])) {
            update_post_meta($wp_post_id, 'siloq_internal_links', $payload['internal_links']);
        }
        
        // Update metadata
        update_post_meta($wp_post_id, 'siloq_content_received_at', current_time('mysql'));
        update_post_meta($wp_post_id, 'siloq_content_status', 'received');
        
        return array(
            'success' => true,
            'post_id' => $wp_post_id,
            'updated' => $updated,
        );
    }
    
    /**
     * Update FAQ schema for post
     */
    private function update_faq_schema($wp_post_id, $faq_items) {
        $schema = array(
            '@context' => 'https://schema.org',
            '@type' => 'FAQPage',
            'mainEntity' => array(),
        );
        
        foreach ($faq_items as $faq) {
            if (!isset($faq['question']) || !isset($faq['answer'])) {
                continue;
            }
            
            $schema['mainEntity'][] = array(
                '@type' => 'Question',
                'name' => $faq['question'],
                'acceptedAnswer' => array(
                    '@type' => 'Answer',
                    'text' => $faq['answer'],
                ),
            );
        }
        
        // Merge with existing schema if present
        $existing_schema = get_post_meta($wp_post_id, 'siloq_jsonld_schema', true);
        if ($existing_schema) {
            if (is_string($existing_schema)) {
                $existing_schema = json_decode($existing_schema, true);
            }
            
            if (is_array($existing_schema)) {
                // If existing is not an array of schemas, wrap it
                if (!isset($existing_schema[0])) {
                    $existing_schema = array($existing_schema);
                }
                
                // Add FAQ schema
                $existing_schema[] = $schema;
                $schema = $existing_schema;
            }
        }
        
        update_post_meta($wp_post_id, 'siloq_jsonld_schema', $schema);
        update_post_meta($wp_post_id, 'siloq_faq_schema', $schema);
    }
    
    /**
     * AJAX handler for syncing a single page
     */
    public function ajax_sync_page() {
        // Check permissions
        if (!current_user_can('edit_posts')) {
            wp_send_json_error(array('message' => 'Insufficient permissions'));
            return;
        }
        
        // Verify nonce
        if (!isset($_POST['nonce']) || !wp_verify_nonce($_POST['nonce'], 'siloq_sync_page')) {
            wp_send_json_error(array('message' => 'Invalid nonce'));
            return;
        }
        
        $post_id = isset($_POST['post_id']) ? intval($_POST['post_id']) : 0;
        
        if (!$post_id) {
            wp_send_json_error(array('message' => 'Invalid post ID'));
            return;
        }
        
        $result = $this->sync_single_post($post_id);
        
        if (is_wp_error($result)) {
            wp_send_json_error(array(
                'message' => $result->get_error_message(),
            ));
        } else {
            wp_send_json_success(array(
                'message' => 'Page synced successfully',
                'data' => $result,
            ));
        }
    }
    
    /**
     * Get sync status for a post
     */
    public function get_sync_status($wp_post_id) {
        $siloq_page_id = $this->api_client->get_siloq_page_id($wp_post_id);
        $last_synced = get_post_meta($wp_post_id, 'siloq_last_synced', true);
        $sync_status = get_post_meta($wp_post_id, 'siloq_sync_status', true);

        return array(
            'siloq_page_id' => $siloq_page_id,
            'last_synced' => $last_synced,
            'sync_status' => $sync_status,
            'is_synced' => !empty($siloq_page_id),
        );
    }

    /**
     * Pull content from Siloq to WordPress
     *
     * @param string $siloq_page_id Siloq page ID
     * @return array|WP_Error Result or error
     */
    public function pull_from_siloq($siloq_page_id) {
        if (!$this->api_client || !$this->api_client->is_configured()) {
            return new WP_Error('not_configured', 'Siloq API is not configured');
        }

        // Get page data from Siloq
        $page_data = $this->api_client->get_page_with_metadata($siloq_page_id);

        if (is_wp_error($page_data)) {
            return $page_data;
        }

        // Find corresponding WordPress post
        global $wpdb;
        $table = $wpdb->prefix . 'siloq_page_mappings';
        $wp_post_id = $wpdb->get_var($wpdb->prepare(
            "SELECT wp_post_id FROM {$table} WHERE siloq_page_id = %s",
            $siloq_page_id
        ));

        if (!$wp_post_id) {
            return new WP_Error('no_mapping', 'No WordPress post found for this Siloq page');
        }

        // Check for conflicts before updating
        $conflict = $this->detect_conflict($wp_post_id, $siloq_page_id);

        if ($conflict === 'conflict') {
            return new WP_Error('conflict_detected', 'Content conflict detected. Both WordPress and Siloq have been modified since last sync.');
        }

        // Update WordPress post with Siloq data
        $post_data = array(
            'ID' => $wp_post_id,
        );

        if (isset($page_data['title'])) {
            $post_data['post_title'] = $page_data['title'];
        }

        if (isset($page_data['body'])) {
            $post_data['post_content'] = wp_kses_post($page_data['body']);
        }

        $result = wp_update_post($post_data, true);

        if (is_wp_error($result)) {
            return $result;
        }

        // Update metadata
        update_post_meta($wp_post_id, 'siloq_last_synced', current_time('mysql'));
        update_post_meta($wp_post_id, 'siloq_sync_status', 'pulled');
        update_post_meta($wp_post_id, 'siloq_sync_direction', 'pull');

        return array(
            'success' => true,
            'wp_post_id' => $wp_post_id,
            'siloq_page_id' => $siloq_page_id,
            'synced_at' => current_time('mysql'),
        );
    }

    /**
     * Bidirectional sync (detects direction automatically)
     *
     * @param int $wp_post_id WordPress post ID
     * @return array|WP_Error Result or error
     */
    public function sync_bidirectional($wp_post_id) {
        $siloq_page_id = $this->api_client->get_siloq_page_id($wp_post_id);

        if (!$siloq_page_id) {
            // No mapping exists, push to Siloq
            return $this->sync_single_post($wp_post_id);
        }

        // Check which side has newer changes
        $conflict_status = $this->detect_conflict($wp_post_id, $siloq_page_id);

        switch ($conflict_status) {
            case 'wordpress_newer':
                return $this->sync_single_post($wp_post_id);

            case 'siloq_newer':
                return $this->pull_from_siloq($siloq_page_id);

            case 'conflict':
                return new WP_Error('conflict_detected', 'Sync conflict detected. Manual resolution required.');

            case 'in_sync':
                return array(
                    'success' => true,
                    'message' => 'Content already in sync',
                    'wp_post_id' => $wp_post_id,
                    'siloq_page_id' => $siloq_page_id,
                );

            default:
                return new WP_Error('unknown_status', 'Unknown conflict status');
        }
    }

    /**
     * Detect sync conflicts
     *
     * @param int $wp_post_id WordPress post ID
     * @param string $siloq_page_id Siloq page ID
     * @return string Conflict status (wordpress_newer, siloq_newer, conflict, in_sync)
     */
    public function detect_conflict($wp_post_id, $siloq_page_id) {
        // Get WordPress post modified time
        $post = get_post($wp_post_id);
        if (!$post) {
            return 'error';
        }

        $wp_modified = strtotime($post->post_modified);

        // Get Siloq page updated time
        $siloq_updated_at = $this->api_client->get_page_updated_at($siloq_page_id);

        if (is_wp_error($siloq_updated_at)) {
            return 'error';
        }

        $siloq_modified = strtotime($siloq_updated_at);

        // Get last sync time
        $last_sync = get_post_meta($wp_post_id, 'siloq_last_synced', true);
        $last_sync_time = $last_sync ? strtotime($last_sync) : 0;

        // Compare modification times
        $wp_changed_since_sync = ($wp_modified > $last_sync_time);
        $siloq_changed_since_sync = ($siloq_modified > $last_sync_time);

        if ($wp_changed_since_sync && $siloq_changed_since_sync) {
            // Both modified since last sync - CONFLICT
            return 'conflict';
        } elseif ($wp_changed_since_sync) {
            // Only WordPress modified
            return 'wordpress_newer';
        } elseif ($siloq_changed_since_sync) {
            // Only Siloq modified
            return 'siloq_newer';
        } else {
            // Neither modified or in sync
            return 'in_sync';
        }
    }

    /**
     * Resolve a sync conflict
     *
     * @param int $wp_post_id WordPress post ID
     * @param string $strategy Resolution strategy (wordpress_wins, siloq_wins, manual, merge)
     * @return array|WP_Error Result or error
     */
    public function resolve_conflict($wp_post_id, $strategy = 'wordpress_wins') {
        $siloq_page_id = $this->api_client->get_siloq_page_id($wp_post_id);

        if (!$siloq_page_id) {
            return new WP_Error('no_mapping', 'No Siloq page mapping found');
        }

        switch ($strategy) {
            case 'wordpress_wins':
                // Push WordPress version to Siloq
                $result = $this->sync_single_post($wp_post_id);
                if (!is_wp_error($result)) {
                    update_post_meta($wp_post_id, 'siloq_conflict_resolved', current_time('mysql'));
                    update_post_meta($wp_post_id, 'siloq_conflict_strategy', 'wordpress_wins');
                }
                return $result;

            case 'siloq_wins':
                // Pull Siloq version to WordPress
                $result = $this->pull_from_siloq($siloq_page_id);
                if (!is_wp_error($result)) {
                    update_post_meta($wp_post_id, 'siloq_conflict_resolved', current_time('mysql'));
                    update_post_meta($wp_post_id, 'siloq_conflict_strategy', 'siloq_wins');
                }
                return $result;

            case 'manual':
                // Flag for manual resolution
                update_post_meta($wp_post_id, 'siloq_conflict_pending', true);
                update_post_meta($wp_post_id, 'siloq_conflict_detected_at', current_time('mysql'));
                return array(
                    'success' => true,
                    'message' => 'Conflict flagged for manual resolution',
                    'wp_post_id' => $wp_post_id,
                );

            case 'merge':
                // Smart merge (not implemented in v2.0)
                return new WP_Error('not_implemented', 'Merge strategy not yet implemented');

            default:
                return new WP_Error('invalid_strategy', 'Invalid conflict resolution strategy');
        }
    }

    /**
     * Batch sync multiple posts
     *
     * @param array $post_ids Array of WordPress post IDs
     * @param string $direction Sync direction (push, pull, bidirectional)
     * @return array Results summary
     */
    public function batch_sync($post_ids, $direction = 'push') {
        if (empty($post_ids) || !is_array($post_ids)) {
            return array(
                'success' => 0,
                'failed' => 0,
                'errors' => array(),
            );
        }

        $success = 0;
        $failed = 0;
        $errors = array();

        foreach ($post_ids as $post_id) {
            $result = null;

            switch ($direction) {
                case 'push':
                    $result = $this->sync_single_post($post_id);
                    break;

                case 'pull':
                    $siloq_page_id = $this->api_client->get_siloq_page_id($post_id);
                    if ($siloq_page_id) {
                        $result = $this->pull_from_siloq($siloq_page_id);
                    } else {
                        $result = new WP_Error('no_mapping', 'No Siloq mapping found');
                    }
                    break;

                case 'bidirectional':
                    $result = $this->sync_bidirectional($post_id);
                    break;
            }

            if (is_wp_error($result)) {
                $failed++;
                $errors[] = array(
                    'post_id' => $post_id,
                    'error' => $result->get_error_message(),
                );
            } else {
                $success++;
            }

            // Rate limiting
            usleep(500000); // 0.5 seconds between requests
        }

        return array(
            'success' => $success,
            'failed' => $failed,
            'total' => count($post_ids),
            'errors' => $errors,
        );
    }
}

