<?php
/**
 * Siloq TALI Access Control
 * 
 * Enforces access state (ENABLED/FROZEN) for authority blocks
 * 
 * @package Siloq_Connector
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_TALI_Access_Control {
    
    /**
     * API client instance
     */
    private $api_client;
    
    /**
     * Cache for claim states (to avoid repeated API calls)
     */
    private $claim_state_cache = array();
    
    /**
     * Constructor
     */
    public function __construct($api_client = null) {
        if (!$api_client) {
            require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-client.php';
            $this->api_client = new Siloq_API_Client();
        } else {
            $this->api_client = $api_client;
        }
    }
    
    /**
     * Render content with access check
     * 
     * @param string $claim_id Claim identifier
     * @param string $content Full content HTML
     * @return string Rendered content (may be suppressed if FROZEN)
     */
    public function render_with_access_check($claim_id, $content) {
        $access_state = $this->get_access_state($claim_id);
        
        if ($access_state === 'FROZEN') {
            return $this->render_frozen_receipt($claim_id);
        }
        
        if ($access_state === 'ENABLED') {
            return $this->render_full_content($claim_id, $content);
        }
        
        // Unknown state - fail safe to frozen
        return $this->render_frozen_receipt($claim_id);
    }
    
    /**
     * Get access state for claim ID
     * 
     * @param string $claim_id Claim identifier
     * @return string Access state (ENABLED or FROZEN)
     */
    public function get_access_state($claim_id) {
        // Check cache first
        if (isset($this->claim_state_cache[$claim_id])) {
            return $this->claim_state_cache[$claim_id];
        }
        
        // Check with Siloq API
        if (!$this->api_client || !$this->api_client->is_configured()) {
            // If API not configured, default to ENABLED (development mode)
            $state = 'ENABLED';
        } else {
            $state = $this->fetch_claim_state($claim_id);
        }
        
        // Cache for this request
        $this->claim_state_cache[$claim_id] = $state;
        
        return $state;
    }
    
    /**
     * Fetch claim state from API
     * 
     * @param string $claim_id Claim identifier
     * @return string Access state
     */
    private function fetch_claim_state($claim_id) {
        try {
            $response = $this->api_client->request('GET', "claims/{$claim_id}/state");
            
            if (is_wp_error($response)) {
                // On API error, fail safe to FROZEN
                return 'FROZEN';
            }
            
            return isset($response['access_state']) ? $response['access_state'] : 'FROZEN';
        } catch (Exception $e) {
            // On exception, fail safe to FROZEN
            error_log("Siloq TALI: Failed to fetch claim state for {$claim_id}: " . $e->getMessage());
            return 'FROZEN';
        }
    }
    
    /**
     * Render frozen receipt (content suppressed, receipt preserved)
     * 
     * @param string $claim_id Claim identifier
     * @return string Frozen receipt HTML
     */
    private function render_frozen_receipt($claim_id) {
        $theme_slug = get_stylesheet();
        
        return sprintf(
            '<div class="siloq-authority-container" 
                  data-siloq-claim-id="%s"
                  data-siloq-governance="V1"
                  data-siloq-access="FROZEN"
                  data-siloq-theme="%s">
              <!-- SiloqAuthorityReceipt: %s -->
              <!-- SiloqNotice: Authority preserved; rendering suppressed due to access state -->
            </div>',
            esc_attr($claim_id),
            esc_attr($theme_slug),
            esc_attr($claim_id)
        );
    }
    
    /**
     * Render full content with authority wrapper
     * 
     * @param string $claim_id Claim identifier
     * @param string $content Content HTML
     * @return string Wrapped content HTML
     */
    private function render_full_content($claim_id, $content) {
        $theme_slug = get_stylesheet();
        
        // Extract template type from content if present
        $template = 'default';
        if (preg_match('/data-siloq-template="([^"]+)"/', $content, $matches)) {
            $template = $matches[1];
        }
        
        // Wrap content with authority container if not already wrapped
        if (strpos($content, 'siloq-authority-container') === false) {
            $content = sprintf(
                '<div class="siloq-authority-container"
                     data-siloq-claim-id="%s"
                     data-siloq-governance="V1"
                     data-siloq-template="%s"
                     data-siloq-theme="%s"
                     data-siloq-access="ENABLED">
                  <!-- SiloqAuthorityReceipt: %s -->
                  %s
                </div>',
                esc_attr($claim_id),
                esc_attr($template),
                esc_attr($theme_slug),
                esc_attr($claim_id),
                $content
            );
        }
        
        return $content;
    }
    
    /**
     * Filter post content to enforce access states
     * 
     * @param string $content Post content
     * @return string Filtered content
     */
    public function filter_post_content($content) {
        if (!is_singular()) {
            return $content;
        }
        
        // Find all authority containers
        $pattern = '/<div[^>]*class="[^"]*siloq-authority-container[^"]*"[^>]*data-siloq-claim-id="([^"]+)"[^>]*>(.*?)<\/div>/s';
        
        $content = preg_replace_callback($pattern, function($matches) {
            $claim_id = $matches[1];
            $block_content = $matches[2];
            
            // Check if already has access state attribute
            if (preg_match('/data-siloq-access="([^"]+)"/', $matches[0], $access_matches)) {
                $access_state = $access_matches[1];
                
                if ($access_state === 'FROZEN') {
                    // Content already frozen, ensure receipt is preserved
                    return $this->render_frozen_receipt($claim_id);
                }
            }
            
            // Check current access state
            return $this->render_with_access_check($claim_id, $matches[0]);
        }, $content);
        
        return $content;
    }
}
