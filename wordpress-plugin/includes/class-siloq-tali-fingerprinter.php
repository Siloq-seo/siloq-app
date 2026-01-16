<?php
/**
 * Siloq TALI Theme Fingerprinter
 * 
 * Fingerprints WordPress theme design tokens and creates design profile
 * 
 * @package Siloq_Connector
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_TALI_Fingerprinter {
    
    /**
     * API client instance
     */
    private $api_client;
    
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
     * Fingerprint theme and create design profile
     */
    public function fingerprint_theme() {
        $profile = array(
            'tali_version' => '1.0',
            'platform' => 'wordpress',
            'theme' => $this->get_theme_info(),
            'tokens' => $this->extract_tokens(),
            'fingerprinted_at' => current_time('c', true)
        );
        
        // Store in WordPress options
        update_option('siloq_design_profile', $profile);
        
        // Also send to Siloq API for centralized storage
        $this->sync_to_api($profile);
        
        return $profile;
    }
    
    /**
     * Get theme information
     */
    private function get_theme_info() {
        $theme = wp_get_theme();
        
        return array(
            'name' => $theme->get('Name'),
            'stylesheet' => get_stylesheet(),
            'is_block_theme' => wp_is_block_theme(),
            'template' => get_template(),
            'version' => $theme->get('Version')
        );
    }
    
    /**
     * Extract design tokens from theme
     */
    private function extract_tokens() {
        return array(
            'colors' => $this->extract_color_tokens(),
            'typography' => $this->extract_typography_tokens(),
            'spacing' => $this->extract_spacing_tokens(),
            'layout' => $this->extract_layout_tokens()
        );
    }
    
    /**
     * Extract color tokens
     */
    private function extract_color_tokens() {
        $colors = array();
        
        // Method 1: Parse theme.json (Block Themes)
        if (wp_is_block_theme()) {
            $theme_json = $this->get_theme_json();
            
            if ($theme_json && isset($theme_json['settings']['color']['palette'])) {
                $palette = $theme_json['settings']['color']['palette'];
                
                foreach ($palette as $color) {
                    if (isset($color['slug']) && isset($color['color'])) {
                        $slug = $color['slug'];
                        $colors[$slug] = $color['color'];
                    }
                }
                
                // Map common slugs to semantic names
                $color_map = array(
                    'primary' => array('primary', 'brand', 'accent'),
                    'secondary' => array('secondary', 'accent-alt'),
                    'text' => array('foreground', 'text', 'body'),
                    'background' => array('background', 'base', 'canvas')
                );
                
                $semantic_colors = array();
                foreach ($color_map as $semantic => $slugs) {
                    foreach ($slugs as $slug) {
                        if (isset($colors[$slug])) {
                            $semantic_colors[$semantic] = $colors[$slug];
                            break;
                        }
                    }
                }
                
                // Fallback to CSS variables
                foreach (array('primary', 'secondary', 'text', 'background') as $key) {
                    if (!isset($semantic_colors[$key])) {
                        $semantic_colors[$key] = $this->get_css_var("--wp--preset--color--{$key}");
                    }
                }
                
                return $semantic_colors;
            }
        }
        
        // Method 2: Compute from CSS variables (fallback)
        return array(
            'primary' => $this->get_css_var('--wp--preset--color--primary') ?: '#0073aa',
            'secondary' => $this->get_css_var('--wp--preset--color--secondary') ?: '#005177',
            'text' => $this->get_css_var('--wp--preset--color--foreground') ?: '#000000',
            'background' => $this->get_css_var('--wp--preset--color--background') ?: '#ffffff',
            'accent' => $this->get_css_var('--wp--preset--color--accent') ?: null
        );
    }
    
    /**
     * Extract typography tokens
     */
    private function extract_typography_tokens() {
        $typography = array();
        
        $theme_json = $this->get_theme_json();
        
        if ($theme_json && isset($theme_json['settings']['typography'])) {
            $typo_settings = $theme_json['settings']['typography'];
            
            // Font family
            if (isset($typo_settings['fontFamily'])) {
                $font_family = $typo_settings['fontFamily'];
                if (isset($font_family['body'])) {
                    $typography['font_family'] = $font_family['body'];
                }
            }
            
            // Font sizes
            if (isset($typo_settings['fontSizes'])) {
                $sizes = $typo_settings['fontSizes'];
                foreach ($sizes as $size) {
                    if (isset($size['slug'])) {
                        $typography['sizes'][$size['slug']] = $size['size'] ?? null;
                    }
                }
            }
        }
        
        // Fallback: Extract from heading styles
        $typography['h1'] = $this->get_heading_style('h1');
        $typography['h2'] = $this->get_heading_style('h2');
        $typography['h3'] = $this->get_heading_style('h3');
        $typography['body'] = $this->get_body_style();
        
        // Font family fallback
        if (!isset($typography['font_family'])) {
            $typography['font_family'] = $this->get_css_var('--wp--preset--font-family--body') 
                ?: 'var(--wp--preset--font-family--system-font)';
        }
        
        return $typography;
    }
    
    /**
     * Extract spacing tokens
     */
    private function extract_spacing_tokens() {
        $spacing = array();
        
        $theme_json = $this->get_theme_json();
        
        if ($theme_json && isset($theme_json['settings']['spacing']['spacingScale'])) {
            $scale = $theme_json['settings']['spacing']['spacingScale'];
            // Parse spacing scale
        }
        
        // Fallback to CSS variables
        $spacing_keys = array('xs', 'sm', 'md', 'lg', 'xl');
        $wp_keys = array('20', '30', '40', '50', '60');
        
        foreach ($spacing_keys as $index => $key) {
            $spacing[$key] = $this->get_css_var("--wp--preset--spacing--{$wp_keys[$index]}") 
                ?: "var(--wp--preset--spacing--{$wp_keys[$index]})";
        }
        
        return $spacing;
    }
    
    /**
     * Extract layout tokens
     */
    private function extract_layout_tokens() {
        return array(
            'content_width' => $this->get_css_var('--wp--style--global--content-size') 
                ?: 'var(--wp--style--global--content-size)',
            'wide_width' => $this->get_css_var('--wp--style--global--wide-size') 
                ?: 'var(--wp--style--global--wide-size)'
        );
    }
    
    /**
     * Get theme.json content
     */
    private function get_theme_json() {
        $theme_json_path = get_stylesheet_directory() . '/theme.json';
        
        if (file_exists($theme_json_path)) {
            $json = file_get_contents($theme_json_path);
            return json_decode($json, true);
        }
        
        // Check parent theme for classic themes
        if (!wp_is_block_theme()) {
            $parent_json_path = get_template_directory() . '/theme.json';
            if (file_exists($parent_json_path)) {
                $json = file_get_contents($parent_json_path);
                return json_decode($json, true);
            }
        }
        
        return null;
    }
    
    /**
     * Get CSS variable value (attempts to read from computed styles)
     * 
     * Note: This is a best-effort approach. Full extraction would require
     * rendering a test page and scraping computed styles.
     */
    private function get_css_var($var_name) {
        // Return variable reference as fallback
        // In production, this could be enhanced with a headless browser
        // to extract actual computed values
        return "var({$var_name})";
    }
    
    /**
     * Get heading style information
     */
    private function get_heading_style($tag) {
        $theme_json = $this->get_theme_json();
        
        if ($theme_json && isset($theme_json['styles']['elements'][$tag])) {
            $heading_styles = $theme_json['styles']['elements'][$tag];
            
            return array(
                'size' => $heading_styles['typography']['fontSize'] ?? null,
                'weight' => $heading_styles['typography']['fontWeight'] ?? null,
                'line_height' => $heading_styles['typography']['lineHeight'] ?? null
            );
        }
        
        // Fallback defaults
        $defaults = array(
            'h1' => array('size' => 'var(--wp--preset--font-size--xx-large)', 'weight' => '700', 'line_height' => '1.2'),
            'h2' => array('size' => 'var(--wp--preset--font-size--x-large)', 'weight' => '600', 'line_height' => '1.3'),
            'h3' => array('size' => 'var(--wp--preset--font-size--large)', 'weight' => '600', 'line_height' => '1.4')
        );
        
        return $defaults[$tag] ?? array('size' => null, 'weight' => null, 'line_height' => null);
    }
    
    /**
     * Get body text style information
     */
    private function get_body_style() {
        $theme_json = $this->get_theme_json();
        
        if ($theme_json && isset($theme_json['styles']['typography'])) {
            $typo = $theme_json['styles']['typography'];
            
            return array(
                'size' => $typo['fontSize'] ?? 'var(--wp--preset--font-size--medium)',
                'weight' => $typo['fontWeight'] ?? '400',
                'line_height' => $typo['lineHeight'] ?? '1.6'
            );
        }
        
        return array(
            'size' => 'var(--wp--preset--font-size--medium)',
            'weight' => '400',
            'line_height' => '1.6'
        );
    }
    
    /**
     * Sync design profile to Siloq API
     */
    private function sync_to_api($profile) {
        if (!$this->api_client || !$this->api_client->is_configured()) {
            return;
        }
        
        $project_id = get_option('siloq_project_id');
        if (!$project_id) {
            return;
        }
        
        // Use API client to sync profile
        // Note: This endpoint will be created in FastAPI
        $this->api_client->request('POST', "projects/{$project_id}/theme-profile", $profile);
    }
}
