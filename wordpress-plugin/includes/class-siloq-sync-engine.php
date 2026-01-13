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
}

