<?php
/**
 * Siloq TALI Confidence Gate
 * 
 * Enforces confidence thresholds and fail-safe rules
 * 
 * @package Siloq_Connector
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_TALI_Confidence_Gate {
    
    /**
     * Confidence threshold (0.90 = 90%)
     */
    const CONFIDENCE_THRESHOLD = 0.90;
    
    /**
     * Check layout confidence before injecting blocks
     * 
     * @param int $page_id WordPress post ID
     * @param string $template Template type (service_city, blog_post, etc.)
     * @return bool True if confidence meets threshold
     */
    public function check_layout_confidence($page_id, $template) {
        $capability_map = get_option('siloq_component_capability_map', array());
        
        if (empty($capability_map) || !isset($capability_map['confidence'])) {
            // If no capability map exists, confidence is unknown - fail safe
            $this->create_as_draft($page_id);
            $this->show_admin_notice($page_id, 0.0, 'Theme capability map not found');
            return false;
        }
        
        $required_components = $this->get_required_components($template);
        $confidence_scores = $capability_map['confidence'];
        
        $min_confidence = 1.0;
        $missing_components = array();
        
        foreach ($required_components as $component) {
            $confidence = isset($confidence_scores[$component]) ? floatval($confidence_scores[$component]) : 0.0;
            $min_confidence = min($min_confidence, $confidence);
            
            if ($confidence < self::CONFIDENCE_THRESHOLD) {
                $missing_components[] = $component;
            }
        }
        
        if ($min_confidence < self::CONFIDENCE_THRESHOLD) {
            $this->create_as_draft($page_id);
            $this->show_admin_notice($page_id, $min_confidence, $missing_components);
            return false;
        }
        
        return true;
    }
    
    /**
     * Get required components for template type
     * 
     * @param string $template Template type
     * @return array Required component names
     */
    private function get_required_components($template) {
        $requirements = array(
            'service_city' => array('group', 'cta_buttons', 'accordion_faq'),
            'blog_post' => array('group', 'tables', 'image_gallery'),
            'project_job' => array('group', 'image_gallery', 'columns')
        );
        
        // Default requirements
        $default = array('group'); // Group block is always required
        
        return isset($requirements[$template]) 
            ? array_merge($default, $requirements[$template])
            : $default;
    }
    
    /**
     * Create page as draft (fail-safe)
     * 
     * @param int $page_id WordPress post ID
     */
    private function create_as_draft($page_id) {
        // Update post status to draft
        wp_update_post(array(
            'ID' => $page_id,
            'post_status' => 'draft'
        ));
        
        // Store reason in post meta
        update_post_meta($page_id, 'siloq_confidence_gate_failed', array(
            'timestamp' => current_time('mysql'),
            'reason' => 'Theme mapping confidence below threshold'
        ));
    }
    
    /**
     * Show admin notice about confidence failure
     * 
     * @param int $page_id WordPress post ID
     * @param float $confidence Confidence score
     * @param mixed $additional_info Additional information (string or array)
     */
    private function show_admin_notice($page_id, $confidence, $additional_info = '') {
        add_action('admin_notices', function() use ($page_id, $confidence, $additional_info) {
            if (get_current_screen()->id !== 'page') {
                return;
            }
            
            $edit_link = get_edit_post_link($page_id);
            $info_text = '';
            
            if (is_array($additional_info)) {
                $info_text = ' Missing components: ' . implode(', ', $additional_info);
            } elseif (!empty($additional_info)) {
                $info_text = ' ' . $additional_info;
            }
            
            printf(
                '<div class="notice notice-warning">
                    <p><strong>Siloq TALI:</strong> Theme mapping confidence below threshold (%.2f).%s 
                    <a href="%s">Review draft layout</a> before publishing.</p>
                </div>',
                $confidence,
                esc_html($info_text),
                esc_url($edit_link)
            );
        });
    }
    
    /**
     * Validate semantic readiness
     * 
     * @param string $content Block content HTML
     * @return bool True if semantically ready
     */
    public function validate_semantic_readiness($content) {
        // Check for required semantic elements
        $has_heading = preg_match('/<h[1-6][^>]*>/i', $content);
        $has_paragraph = preg_match('/<p[^>]*>/i', $content);
        
        // Content must exist in HTML source (SSR requirement)
        if (empty($content) || (!$has_heading && !$has_paragraph)) {
            return false;
        }
        
        // Check for claim anchor (receipt comment)
        $has_receipt = strpos($content, 'SiloqAuthorityReceipt:') !== false;
        
        return $has_receipt;
    }
    
    /**
     * Validate wrapper requirements
     * 
     * @param string $content Block content HTML
     * @return bool True if wrapper requirements met
     */
    public function validate_wrapper_requirements($content) {
        // Must have authority container wrapper
        $has_wrapper = strpos($content, 'siloq-authority-container') !== false;
        
        // Must have claim ID attribute
        $has_claim_id = preg_match('/data-siloq-claim-id="([^"]+)"/', $content);
        
        // Must have governance version
        $has_governance = strpos($content, 'data-siloq-governance') !== false;
        
        return $has_wrapper && $has_claim_id && $has_governance;
    }
    
    /**
     * Validate claim anchor presence
     * 
     * @param string $content Block content HTML
     * @return bool True if claim anchor present
     */
    public function validate_claim_anchor($content) {
        // Must have receipt comment
        $has_receipt_comment = strpos($content, '<!-- SiloqAuthorityReceipt:') !== false;
        
        return $has_receipt_comment;
    }
    
    /**
     * Comprehensive validation before publishing
     * 
     * @param int $page_id WordPress post ID
     * @param string $content Page content
     * @param string $template Template type
     * @return array Validation result
     */
    public function validate_before_publish($page_id, $content, $template) {
        $errors = array();
        $warnings = array();
        
        // 1. Check layout confidence
        if (!$this->check_layout_confidence($page_id, $template)) {
            $errors[] = 'Theme mapping confidence below threshold (0.90)';
        }
        
        // 2. Validate semantic readiness
        if (!$this->validate_semantic_readiness($content)) {
            $errors[] = 'Content does not meet semantic readiness requirements (missing headings/paragraphs or receipt)';
        }
        
        // 3. Validate wrapper requirements
        if (!$this->validate_wrapper_requirements($content)) {
            $errors[] = 'Authority wrapper requirements not met (missing container, claim ID, or governance version)';
        }
        
        // 4. Validate claim anchor presence
        if (!$this->validate_claim_anchor($content)) {
            $errors[] = 'Claim anchor receipt not found in content';
        }
        
        return array(
            'valid' => empty($errors),
            'errors' => $errors,
            'warnings' => $warnings
        );
    }
}
