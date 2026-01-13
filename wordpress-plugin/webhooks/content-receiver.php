<?php
/**
 * Siloq Webhook Receiver
 * 
 * Receives content updates from Siloq platform
 */

// Exit if accessed directly
if (!defined('ABSPATH')) {
    // This is a direct webhook call, not through WordPress
    // Load WordPress
    $wp_load_path = dirname(dirname(dirname(dirname(__FILE__)))) . '/wp-load.php';
    
    if (file_exists($wp_load_path)) {
        require_once $wp_load_path;
    } else {
        http_response_code(500);
        echo json_encode(array('error' => 'WordPress not found'));
        exit;
    }
}

// Verify webhook signature if configured
$webhook_secret = get_option('siloq_webhook_secret', '');
if (!empty($webhook_secret)) {
    $signature = isset($_SERVER['HTTP_X_SILOQ_SIGNATURE']) ? $_SERVER['HTTP_X_SILOQ_SIGNATURE'] : '';
    $payload = file_get_contents('php://input');
    $expected_signature = hash_hmac('sha256', $payload, $webhook_secret);
    
    if (!hash_equals($expected_signature, $signature)) {
        http_response_code(401);
        echo json_encode(array('error' => 'Invalid signature'));
        exit;
    }
}

// Get request body
$payload = json_decode(file_get_contents('php://input'), true);

if (json_last_error() !== JSON_ERROR_NONE) {
    http_response_code(400);
    echo json_encode(array('error' => 'Invalid JSON'));
    exit;
}

// Validate payload
if (!isset($payload['event_type']) || !isset($payload['data'])) {
    http_response_code(400);
    echo json_encode(array('error' => 'Missing required fields'));
    exit;
}

// Load required classes
require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-client.php';
require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-sync-engine.php';

$api_client = new Siloq_API_Client();
$sync_engine = new Siloq_Sync_Engine($api_client);

$event_type = $payload['event_type'];
$data = $payload['data'];

$response = array('success' => false, 'message' => '');

// Handle different event types
switch ($event_type) {
    case 'content.updated':
        // Content has been generated/updated in Siloq
        if (!isset($data['wp_post_id']) || !isset($data['html_content'])) {
            $response['message'] = 'Missing required fields: wp_post_id, html_content';
            break;
        }
        
        $result = $sync_engine->receive_from_siloq($data);
        
        if (is_wp_error($result)) {
            $response['message'] = $result->get_error_message();
        } else {
            $response['success'] = true;
            $response['message'] = 'Content updated successfully';
            $response['data'] = $result;
        }
        break;
        
    case 'schema.updated':
        // JSON-LD schema has been updated
        if (!isset($data['wp_post_id']) || !isset($data['jsonld_schema'])) {
            $response['message'] = 'Missing required fields: wp_post_id, jsonld_schema';
            break;
        }
        
        update_post_meta($data['wp_post_id'], 'siloq_jsonld_schema', $data['jsonld_schema']);
        
        $response['success'] = true;
        $response['message'] = 'Schema updated successfully';
        break;
        
    case 'redirect.created':
        // Redirect has been created in Siloq
        if (!isset($data['source_url']) || !isset($data['target_url'])) {
            $response['message'] = 'Missing required fields: source_url, target_url';
            break;
        }
        
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-redirect-manager.php';
        $redirect_manager = new Siloq_Redirect_Manager();
        
        $redirect_manager->apply_redirect(
            $data['source_url'],
            $data['target_url'],
            isset($data['redirect_type']) ? $data['redirect_type'] : 301
        );
        
        $response['success'] = true;
        $response['message'] = 'Redirect applied successfully';
        break;
        
    case 'links.updated':
        // Internal links have been updated
        if (!isset($data['wp_post_id']) || !isset($data['internal_links'])) {
            $response['message'] = 'Missing required fields: wp_post_id, internal_links';
            break;
        }
        
        update_post_meta($data['wp_post_id'], 'siloq_internal_links', $data['internal_links']);
        
        $response['success'] = true;
        $response['message'] = 'Internal links updated successfully';
        break;
        
    case 'page.published':
        // Page has been published in Siloq
        if (!isset($data['wp_post_id'])) {
            $response['message'] = 'Missing required field: wp_post_id';
            break;
        }
        
        // Update post meta to indicate published status
        update_post_meta($data['wp_post_id'], 'siloq_published_at', current_time('mysql'));
        update_post_meta($data['wp_post_id'], 'siloq_publish_status', 'published');
        
        $response['success'] = true;
        $response['message'] = 'Publish status updated';
        break;
        
    default:
        $response['message'] = 'Unknown event type: ' . $event_type;
        break;
}

// Log webhook event
if (function_exists('error_log')) {
    error_log('Siloq webhook received: ' . $event_type . ' - ' . ($response['success'] ? 'success' : 'failed'));
}

// Send response
http_response_code($response['success'] ? 200 : 400);
header('Content-Type: application/json');
echo json_encode($response);
exit;

