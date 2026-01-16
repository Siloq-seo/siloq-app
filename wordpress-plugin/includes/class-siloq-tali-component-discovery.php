<?php
/**
 * Siloq TALI Component Discovery
 * 
 * Discovers theme component capabilities and creates capability map
 * 
 * @package Siloq_Connector
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_TALI_Component_Discovery {
    
    /**
     * Discover theme component capabilities
     */
    public function discover_capabilities() {
        $capabilities = array(
            'supports' => $this->detect_supported_components(),
            'confidence' => $this->calculate_confidence_scores()
        );
        
        // Store in WordPress options
        update_option('siloq_component_capability_map', $capabilities);
        
        return $capabilities;
    }
    
    /**
     * Detect supported components
     */
    private function detect_supported_components() {
        return array(
            'cta_buttons' => $this->has_button_styles(),
            'grid_layout' => $this->has_grid_patterns(),
            'accordion_faq' => $this->has_accordion_blocks(),
            'tables' => $this->has_table_support(),
            'testimonials' => $this->has_testimonial_blocks(),
            'image_gallery' => $this->has_gallery_support(),
            'columns' => $this->has_columns_support(),
            'group' => $this->has_group_support()
        );
    }
    
    /**
     * Check if theme has button block styles
     */
    private function has_button_styles() {
        if (!class_exists('WP_Block_Styles_Registry')) {
            return false;
        }
        
        $registry = WP_Block_Styles_Registry::get_instance();
        $styles = $registry->get_registered_styles('core/button');
        
        return !empty($styles);
    }
    
    /**
     * Check if theme supports grid/columns layout
     */
    private function has_grid_patterns() {
        // Check for columns block support
        if (function_exists('has_block_support')) {
            return has_block_support('core/columns', 'spacing') || 
                   has_block_support('core/columns', 'color');
        }
        
        // Fallback: Check theme.json
        $theme_json = $this->get_theme_json();
        if ($theme_json && isset($theme_json['settings']['layout'])) {
            return true;
        }
        
        return false;
    }
    
    /**
     * Check if theme has accordion/FAQ blocks
     */
    private function has_accordion_blocks() {
        // Check for details block (WP 6.4+)
        if (function_exists('register_block_type')) {
            // Details block is core since WP 6.4
            global $wp_version;
            if (version_compare($wp_version, '6.4', '>=')) {
                return true;
            }
        }
        
        // Check for custom accordion blocks
        $blocks = get_dynamic_block_names();
        if (in_array('core/details', $blocks) || 
            in_array('siloq/accordion', $blocks)) {
            return true;
        }
        
        return false;
    }
    
    /**
     * Check if theme has table support
     */
    private function has_table_support() {
        // Table block is core WordPress
        return function_exists('register_block_type') && 
               $this->is_block_registered('core/table');
    }
    
    /**
     * Check if theme has testimonial blocks
     */
    private function has_testimonial_blocks() {
        // Check for quote block (can be styled as testimonial)
        if ($this->is_block_registered('core/quote')) {
            return true;
        }
        
        // Check for custom testimonial blocks
        $blocks = get_dynamic_block_names();
        return in_array('siloq/testimonial', $blocks);
    }
    
    /**
     * Check if theme has gallery support
     */
    private function has_gallery_support() {
        return $this->is_block_registered('core/gallery') || 
               $this->is_block_registered('core/image');
    }
    
    /**
     * Check if theme supports columns block
     */
    private function has_columns_support() {
        return $this->is_block_registered('core/columns');
    }
    
    /**
     * Check if theme supports group block
     */
    private function has_group_support() {
        return $this->is_block_registered('core/group');
    }
    
    /**
     * Check if block is registered
     */
    private function is_block_registered($block_name) {
        $registry = WP_Block_Type_Registry::get_instance();
        return $registry->is_registered($block_name);
    }
    
    /**
     * Calculate confidence scores for each component
     */
    private function calculate_confidence_scores() {
        $scores = array();
        $supports = $this->detect_supported_components();
        
        // Button confidence based on registered styles
        if (isset($supports['cta_buttons']) && $supports['cta_buttons']) {
            $registry = WP_Block_Styles_Registry::get_instance();
            $button_styles = $registry->get_registered_styles('core/button');
            $scores['cta_buttons'] = count($button_styles) > 0 ? 0.95 : 0.7;
        } else {
            $scores['cta_buttons'] = 0.3;
        }
        
        // Grid confidence based on theme.json layout settings
        $theme_json = $this->get_theme_json();
        if (isset($supports['grid_layout']) && $supports['grid_layout']) {
            $scores['grid_layout'] = isset($theme_json['settings']['layout']) ? 0.9 : 0.7;
        } else {
            $scores['grid_layout'] = 0.5;
        }
        
        // Accordion confidence
        if (isset($supports['accordion_faq']) && $supports['accordion_faq']) {
            global $wp_version;
            $scores['accordion_faq'] = version_compare($wp_version, '6.4', '>=') ? 0.95 : 0.7;
        } else {
            $scores['accordion_faq'] = 0.3;
        }
        
        // Table confidence (core block = high confidence)
        $scores['tables'] = isset($supports['tables']) && $supports['tables'] ? 1.0 : 0.0;
        
        // Testimonial confidence
        $scores['testimonials'] = isset($supports['testimonials']) && $supports['testimonials'] ? 0.8 : 0.0;
        
        // Gallery confidence (core block = high confidence)
        $scores['image_gallery'] = isset($supports['image_gallery']) && $supports['image_gallery'] ? 0.85 : 0.0;
        
        // Columns confidence
        $scores['columns'] = isset($supports['columns']) && $supports['columns'] ? 0.95 : 0.0;
        
        // Group confidence
        $scores['group'] = isset($supports['group']) && $supports['group'] ? 1.0 : 0.0;
        
        return $scores;
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
        
        return null;
    }
}
