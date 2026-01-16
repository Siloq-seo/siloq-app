<?php
/**
 * Siloq Schema Injector
 * 
 * Handles JSON-LD schema injection into WordPress pages
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Schema_Injector {
    
    /**
     * Inject schema for a post
     */
    public function inject_schema($wp_post_id, $schema) {
        // Validate schema
        if (!is_array($schema)) {
            if (is_string($schema)) {
                $schema = json_decode($schema, true);
            } else {
                return new WP_Error('invalid_schema', 'Schema must be an array or valid JSON string');
            }
        }
        
        // Validate JSON-LD structure
        if (!isset($schema['@context'])) {
            $schema['@context'] = 'https://schema.org';
        }
        
        // Store schema
        update_post_meta($wp_post_id, 'siloq_jsonld_schema', $schema);
        
        return true;
    }
    
    /**
     * Get schema for a post
     */
    public function get_schema($wp_post_id) {
        return get_post_meta($wp_post_id, 'siloq_jsonld_schema', true);
    }
    
    /**
     * Update schema from Siloq API
     */
    public function update_from_siloq($wp_post_id, $api_client) {
        $siloq_page_id = $api_client->get_siloq_page_id($wp_post_id);
        
        if (!$siloq_page_id) {
            return new WP_Error('not_synced', 'Page not synced to Siloq');
        }
        
        $result = $api_client->get_page_jsonld($siloq_page_id);
        
        if (is_wp_error($result)) {
            return $result;
        }
        
        return $this->inject_schema($wp_post_id, $result);
    }
    
    /**
     * Generate basic schema for a post
     */
    public function generate_basic_schema($wp_post_id) {
        $post = get_post($wp_post_id);
        if (!$post) {
            return null;
        }
        
        $schema = array(
            '@context' => 'https://schema.org',
            '@type' => $post->post_type === 'page' ? 'WebPage' : 'Article',
            'headline' => $post->post_title,
            'description' => wp_trim_words($post->post_excerpt ?: $post->post_content, 25),
            'url' => get_permalink($wp_post_id),
            'datePublished' => get_the_date('c', $wp_post_id),
            'dateModified' => get_the_modified_date('c', $wp_post_id),
            'author' => array(
                '@type' => 'Person',
                'name' => get_the_author_meta('display_name', $post->post_author),
            ),
            'publisher' => array(
                '@type' => 'Organization',
                'name' => get_bloginfo('name'),
                'url' => home_url(),
            ),
        );
        
        // Add featured image if available
        $thumbnail_id = get_post_thumbnail_id($wp_post_id);
        if ($thumbnail_id) {
            $image_url = wp_get_attachment_image_url($thumbnail_id, 'full');
            $schema['image'] = $image_url;
        }
        
        return $schema;
    }
    
    /**
     * Merge multiple schemas
     */
    public function merge_schemas($schemas) {
        if (empty($schemas)) {
            return null;
        }
        
        // If single schema, return as-is
        if (count($schemas) === 1) {
            return $schemas[0];
        }
        
        // Multiple schemas - return as array
        return $schemas;
    }
}

