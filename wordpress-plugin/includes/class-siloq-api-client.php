<?php
/**
 * Siloq API Client
 * 
 * Handles all communication with the Siloq API platform
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_API_Client {
    
    /**
     * API base URL
     */
    private $api_base_url;
    
    /**
     * API key
     */
    private $api_key;
    
    /**
     * Site ID in Siloq
     */
    private $siloq_site_id;
    
    /**
     * Constructor
     */
    public function __construct() {
        $this->api_base_url = get_option('siloq_api_base_url', 'https://api.siloq.io/v1');
        $this->api_key = get_option('siloq_api_key', '');
        $this->siloq_site_id = get_option('siloq_site_id', '');
    }
    
    /**
     * Check if API is configured
     */
    public function is_configured() {
        return !empty($this->api_key) && !empty($this->siloq_site_id);
    }
    
    /**
     * Make API request
     */
    private function request($method, $endpoint, $body = null, $headers = array()) {
        if (!$this->is_configured()) {
            return new WP_Error('not_configured', 'Siloq API is not configured. Please enter your API key and Site ID in settings.');
        }
        
        $url = rtrim($this->api_base_url, '/') . '/' . ltrim($endpoint, '/');
        
        $default_headers = array(
            'Authorization' => 'Bearer ' . $this->api_key,
            'Content-Type' => 'application/json',
            'Accept' => 'application/json',
        );
        
        $headers = array_merge($default_headers, $headers);
        
        $args = array(
            'method' => $method,
            'headers' => $headers,
            'timeout' => 30,
        );
        
        if ($body !== null) {
            $args['body'] = json_encode($body);
        }
        
        $response = wp_remote_request($url, $args);
        
        if (is_wp_error($response)) {
            return $response;
        }
        
        $status_code = wp_remote_retrieve_response_code($response);
        $body = wp_remote_retrieve_body($response);
        $data = json_decode($body, true);
        
        if ($status_code >= 200 && $status_code < 300) {
            return $data;
        }
        
        // Handle error response
        $error_message = isset($data['detail']) ? $data['detail'] : 'API request failed';
        if (is_array($error_message)) {
            $error_message = isset($error_message['message']) ? $error_message['message'] : json_encode($error_message);
        }
        
        return new WP_Error(
            'api_error',
            $error_message,
            array(
                'status_code' => $status_code,
                'response' => $data,
            )
        );
    }
    
    /**
     * Validate page in Siloq
     */
    public function validate_page($wp_post_id) {
        $post = get_post($wp_post_id);
        if (!$post) {
            return new WP_Error('invalid_post', 'Post not found');
        }
        
        // Get or create Siloq page mapping
        $siloq_page_id = $this->get_siloq_page_id($wp_post_id);
        
        if (!$siloq_page_id) {
            // Create page first
            $result = $this->create_page($wp_post_id);
            if (is_wp_error($result)) {
                return $result;
            }
            $siloq_page_id = $result['id'];
        }
        
        $payload = array(
            'page_id' => $siloq_page_id,
            'url' => get_permalink($wp_post_id),
            'page_type' => $this->determine_page_type($post),
            'intent' => $this->determine_intent($post),
        );
        
        return $this->request('POST', "pages/{$siloq_page_id}/validate", $payload);
    }
    
    /**
     * Create page in Siloq
     */
    public function create_page($wp_post_id) {
        $post = get_post($wp_post_id);
        if (!$post) {
            return new WP_Error('invalid_post', 'Post not found');
        }
        
        $payload = array(
            'title' => $post->post_title,
            'path' => wp_parse_url(get_permalink($wp_post_id), PHP_URL_PATH),
            'site_id' => $this->siloq_site_id,
            'prompt' => $this->generate_prompt_from_post($post),
            'metadata' => array(
                'wp_post_id' => $wp_post_id,
                'wp_post_type' => $post->post_type,
                'wp_url' => get_permalink($wp_post_id),
            ),
        );
        
        $result = $this->request('POST', 'pages', $payload);
        
        if (!is_wp_error($result) && isset($result['id'])) {
            // Store mapping
            $this->store_page_mapping($wp_post_id, $result['id']);
        }
        
        return $result;
    }
    
    /**
     * Update page in Siloq
     */
    public function update_page($wp_post_id, $siloq_page_id = null) {
        if (!$siloq_page_id) {
            $siloq_page_id = $this->get_siloq_page_id($wp_post_id);
        }
        
        if (!$siloq_page_id) {
            return $this->create_page($wp_post_id);
        }
        
        $post = get_post($wp_post_id);
        if (!$post) {
            return new WP_Error('invalid_post', 'Post not found');
        }
        
        $payload = array(
            'title' => $post->post_title,
            'body' => $post->post_content,
            'path' => wp_parse_url(get_permalink($wp_post_id), PHP_URL_PATH),
        );
        
        return $this->request('PUT', "pages/{$siloq_page_id}", $payload);
    }
    
    /**
     * Get page JSON-LD schema
     */
    public function get_page_jsonld($siloq_page_id) {
        return $this->request('GET', "pages/{$siloq_page_id}/jsonld");
    }
    
    /**
     * Get page details
     */
    public function get_page($siloq_page_id) {
        return $this->request('GET', "pages/{$siloq_page_id}");
    }
    
    /**
     * Publish page in Siloq
     */
    public function publish_page($siloq_page_id) {
        return $this->request('POST', "pages/{$siloq_page_id}/publish");
    }
    
    /**
     * Check publish gates
     */
    public function check_publish_gates($siloq_page_id) {
        return $this->request('GET', "pages/{$siloq_page_id}/gates");
    }
    
    /**
     * Get job status
     */
    public function get_job_status($job_id) {
        return $this->request('GET', "jobs/{$job_id}");
    }
    
    /**
     * Transition job state
     */
    public function transition_job_state($job_id, $target_state, $reason = '') {
        $payload = array(
            'target_state' => $target_state,
            'reason' => $reason,
        );
        
        return $this->request('POST', "jobs/{$job_id}/transition", $payload);
    }
    
    /**
     * Store page mapping between WordPress and Siloq
     */
    private function store_page_mapping($wp_post_id, $siloq_page_id) {
        global $wpdb;
        
        $table = $wpdb->prefix . 'siloq_page_mappings';
        
        $wpdb->replace(
            $table,
            array(
                'wp_post_id' => $wp_post_id,
                'siloq_page_id' => $siloq_page_id,
                'synced_at' => current_time('mysql'),
            ),
            array('%d', '%s', '%s')
        );
    }
    
    /**
     * Get Siloq page ID for WordPress post
     */
    public function get_siloq_page_id($wp_post_id) {
        global $wpdb;
        
        $table = $wpdb->prefix . 'siloq_page_mappings';
        $siloq_page_id = $wpdb->get_var($wpdb->prepare(
            "SELECT siloq_page_id FROM {$table} WHERE wp_post_id = %d",
            $wp_post_id
        ));
        
        return $siloq_page_id;
    }
    
    /**
     * Determine page type from WordPress post
     */
    private function determine_page_type($post) {
        // Default to 'target' for pages
        if ($post->post_type === 'page') {
            return 'target';
        }
        
        // Could be enhanced to detect pillar, supporting, etc.
        return 'target';
    }
    
    /**
     * Determine intent from WordPress post
     */
    private function determine_intent($post) {
        // Try to detect from post meta or content
        $intent = get_post_meta($post->ID, 'siloq_intent', true);
        
        if ($intent) {
            return $intent;
        }
        
        // Default to commercial for pages, informational for posts
        return $post->post_type === 'page' ? 'commercial' : 'informational';
    }
    
    /**
     * Generate prompt from WordPress post
     */
    private function generate_prompt_from_post($post) {
        $prompt = "Generate SEO-optimized content for: " . $post->post_title;
        
        if (!empty($post->post_excerpt)) {
            $prompt .= "\n\nExcerpt: " . $post->post_excerpt;
        }
        
        // Add custom prompt if available
        $custom_prompt = get_post_meta($post->ID, 'siloq_custom_prompt', true);
        if ($custom_prompt) {
            $prompt = $custom_prompt;
        }
        
        return $prompt;
    }
    
    /**
     * Test API connection
     */
    public function test_connection() {
        return $this->request('GET', 'sites/' . $this->siloq_site_id);
    }
    
    /**
     * Sync theme profile to Siloq API
     * 
     * @param array $profile Theme design profile
     * @return array|WP_Error API response
     */
    public function sync_theme_profile($profile) {
        $project_id = get_option('siloq_project_id');
        if (!$project_id) {
            return new WP_Error('no_project_id', 'Siloq project ID not configured');
        }
        
        return $this->request('POST', "wordpress/projects/{$project_id}/theme-profile", $profile);
    }
    
    /**
     * Get claim state from Siloq API
     * 
     * @param string $claim_id Claim identifier
     * @return array|WP_Error API response
     */
    public function get_claim_state($claim_id) {
        return $this->request('GET', "wordpress/claims/{$claim_id}/state");
    }
    
    /**
     * Sync WordPress page to Siloq
     * 
     * @param int $wp_post_id WordPress post ID
     * @param array $page_data Page data
     * @return array|WP_Error API response
     */
    public function sync_wordpress_page($wp_post_id, $page_data) {
        $project_id = get_option('siloq_project_id');
        if (!$project_id) {
            return new WP_Error('no_project_id', 'Siloq project ID not configured');
        }
        
        $payload = array_merge($page_data, array(
            'wordpress_post_id' => $wp_post_id,
        ));
        
        return $this->request('POST', "wordpress/projects/{$project_id}/pages/sync", $payload);
    }
}

