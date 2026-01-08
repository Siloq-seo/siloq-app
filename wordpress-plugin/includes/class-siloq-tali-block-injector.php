<?php
/**
 * Siloq TALI Authority Block Injector
 * 
 * Injects authority blocks with claim anchors into WordPress Gutenberg blocks
 * 
 * @package Siloq_Connector
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_TALI_Block_Injector {
    
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
     * Inject authority blocks into page content
     * 
     * @param int $page_id WordPress post ID
     * @param array $content_data Content sections from Siloq
     * @param array $claim_manifest Claim IDs for each section
     * @return string Serialized Gutenberg blocks
     */
    public function inject_authority_blocks($page_id, $content_data, $claim_manifest = array()) {
        $blocks = array();
        
        if (!isset($content_data['sections']) || !is_array($content_data['sections'])) {
            return '';
        }
        
        foreach ($content_data['sections'] as $index => $section) {
            // Get claim ID from manifest or generate
            $claim_id = isset($claim_manifest[$index]) 
                ? $claim_manifest[$index] 
                : $this->generate_claim_id($section, $page_id);
            
            $block = $this->create_wrapped_block(
                $section,
                $claim_id,
                isset($section['type']) ? $section['type'] : 'default'
            );
            
            $blocks[] = $block;
        }
        
        return $this->serialize_blocks($blocks);
    }
    
    /**
     * Create wrapped block with authority container
     * 
     * @param array $section Content section data
     * @param string $claim_id Claim identifier
     * @param string $type Section type (service_city, blog_post, etc.)
     * @return array Block data structure
     */
    private function create_wrapped_block($section, $claim_id, $type) {
        $theme_slug = get_stylesheet();
        
        $wrapper_attrs = array(
            'className' => 'siloq-authority-container',
            'data-siloq-claim-id' => $claim_id,
            'data-siloq-governance' => 'V1',
            'data-siloq-template' => $type,
            'data-siloq-theme' => $theme_slug
        );
        
        // Start with receipt comment
        $html = "<!-- SiloqAuthorityReceipt: {$claim_id} -->\n";
        
        // Add semantic content
        $html .= $this->render_semantic_content($section);
        
        return array(
            'blockName' => 'core/group',
            'attrs' => $wrapper_attrs,
            'innerContent' => array($html)
        );
    }
    
    /**
     * Render semantic HTML content
     * 
     * @param array $content Content data
     * @return string HTML content
     */
    private function render_semantic_content($content) {
        $html = '';
        
        // Heading
        if (!empty($content['heading'])) {
            $level = isset($content['heading_level']) ? intval($content['heading_level']) : 2;
            $html .= sprintf(
                '<h%d class="wp-block-heading">%s</h%d>',
                $level,
                esc_html($content['heading']),
                $level
            ) . "\n";
        }
        
        // Paragraphs
        if (!empty($content['paragraphs']) && is_array($content['paragraphs'])) {
            foreach ($content['paragraphs'] as $para) {
                $html .= sprintf(
                    '<p class="wp-block-paragraph">%s</p>',
                    wp_kses_post($para)
                ) . "\n";
            }
        }
        
        // Lists
        if (!empty($content['list']) && is_array($content['list'])) {
            $list_type = isset($content['list_type']) && $content['list_type'] === 'ordered' ? 'ol' : 'ul';
            $html .= "<{$list_type} class=\"wp-block-list\">\n";
            foreach ($content['list'] as $item) {
                $html .= sprintf('<li>%s</li>', esc_html($item)) . "\n";
            }
            $html .= "</{$list_type}>\n";
        }
        
        // FAQ Section with microdata
        if (!empty($content['faqs']) && is_array($content['faqs'])) {
            $html .= $this->render_faq_section($content['faqs']);
        }
        
        // Buttons/CTAs
        if (!empty($content['cta']) && is_array($content['cta'])) {
            $html .= $this->render_cta_buttons($content['cta']);
        }
        
        return $html;
    }
    
    /**
     * Render FAQ section with Schema.org microdata
     * 
     * @param array $faqs FAQ items
     * @return string HTML for FAQ section
     */
    private function render_faq_section($faqs) {
        $html = '<div class="wp-block-group siloq-faq-section" itemscope itemtype="https://schema.org/FAQPage">' . "\n";
        
        foreach ($faqs as $faq) {
            if (empty($faq['question']) || empty($faq['answer'])) {
                continue;
            }
            
            $html .= '<div class="faq-item" itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">' . "\n";
            
            // Question
            $html .= sprintf(
                '<h3 class="wp-block-heading faq-question" itemprop="name">%s</h3>',
                esc_html($faq['question'])
            ) . "\n";
            
            // Answer
            $html .= '<div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">' . "\n";
            $html .= sprintf(
                '<div itemprop="text">%s</div>',
                wp_kses_post($faq['answer'])
            ) . "\n";
            $html .= '</div>' . "\n"; // acceptedAnswer
            
            $html .= '</div>' . "\n"; // faq-item
        }
        
        $html .= '</div>' . "\n"; // faq-section
        
        return $html;
    }
    
    /**
     * Render CTA buttons
     * 
     * @param array $cta_items CTA button data
     * @return string HTML for CTA buttons
     */
    private function render_cta_buttons($cta_items) {
        $html = '<div class="wp-block-buttons">' . "\n";
        
        foreach ($cta_items as $cta) {
            if (empty($cta['text']) || empty($cta['url'])) {
                continue;
            }
            
            $html .= '<div class="wp-block-button">' . "\n";
            $html .= sprintf(
                '<a class="wp-block-button__link" href="%s">%s</a>',
                esc_url($cta['url']),
                esc_html($cta['text'])
            ) . "\n";
            $html .= '</div>' . "\n";
        }
        
        $html .= '</div>' . "\n";
        
        return $html;
    }
    
    /**
     * Generate deterministic claim ID
     * 
     * @param array $section Content section
     * @param int $page_id WordPress post ID
     * @return string Claim ID (format: CLAIM:TYPE-HASH)
     */
    private function generate_claim_id($section, $page_id) {
        $type = isset($section['type']) ? strtoupper($section['type']) : 'UNK';
        $heading = isset($section['heading']) ? $section['heading'] : '';
        
        // Create deterministic hash
        $hash_input = $page_id . $heading . $type;
        $hash = substr(md5($hash_input), 0, 8);
        
        return sprintf('CLAIM:%s-%s', $type, strtoupper($hash));
    }
    
    /**
     * Serialize blocks to Gutenberg format
     * 
     * @param array $blocks Block data structures
     * @return string Serialized block markup
     */
    private function serialize_blocks($blocks) {
        $output = '';
        
        foreach ($blocks as $block) {
            $output .= $this->serialize_single_block($block);
        }
        
        return $output;
    }
    
    /**
     * Serialize single block to Gutenberg format
     * 
     * @param array $block Block data
     * @return string Serialized block markup
     */
    private function serialize_single_block($block) {
        $block_name = isset($block['blockName']) ? $block['blockName'] : 'core/group';
        $attrs = isset($block['attrs']) ? $block['attrs'] : array();
        $inner_content = isset($block['innerContent']) ? $block['innerContent'] : array();
        
        // Serialize attributes to JSON
        $attrs_json = !empty($attrs) ? ' ' . wp_json_encode($attrs) : '';
        
        // Build block markup
        $markup = "<!-- wp:{$block_name}{$attrs_json} -->\n";
        
        foreach ($inner_content as $content) {
            if (is_string($content)) {
                $markup .= $content;
                if (substr($content, -1) !== "\n") {
                    $markup .= "\n";
                }
            }
        }
        
        $markup .= "<!-- /wp:{$block_name} -->\n";
        
        return $markup;
    }
    
    /**
     * Convert serialized blocks to WordPress post content
     * 
     * @param string $serialized_blocks Gutenberg block markup
     * @return string WordPress post content
     */
    public function blocks_to_content($serialized_blocks) {
        // For WordPress 5.0+, Gutenberg blocks are stored as-is
        // This function can be enhanced to convert to classic editor format if needed
        return $serialized_blocks;
    }
}
