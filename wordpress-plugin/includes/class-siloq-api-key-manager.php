<?php
/**
 * Siloq API Key Manager
 *
 * Handles API key lifecycle management including generation, validation, rotation, and revocation
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_API_Key_Manager {

    /**
     * API client instance
     */
    private $api_client;

    /**
     * Option name for storing encrypted API key
     */
    const API_KEY_OPTION = 'siloq_api_key';

    /**
     * Option name for storing API key metadata
     */
    const API_KEY_META_OPTION = 'siloq_api_key_meta';

    /**
     * Constructor
     */
    public function __construct($api_client = null) {
        $this->api_client = $api_client;
    }

    /**
     * Generate a new API key for the WordPress site
     *
     * @param string $name Optional name for the API key
     * @return array|WP_Error API key data or error
     */
    public function generate_api_key($name = 'WordPress Plugin') {
        if (!$this->api_client) {
            return new WP_Error('no_api_client', 'API client not initialized');
        }

        $site_id = get_option('siloq_site_id', '');
        if (empty($site_id)) {
            return new WP_Error('no_site_id', 'Site ID not configured. Please configure your Siloq site first.');
        }

        // Get site URL for the API key name
        $site_url = get_site_url();
        $default_name = 'WordPress Plugin - ' . parse_url($site_url, PHP_URL_HOST);

        $payload = array(
            'name' => !empty($name) ? $name : $default_name,
            'description' => 'Generated from WordPress plugin at ' . $site_url,
            'scopes' => array(
                'pages:read',
                'pages:write',
                'pages:publish',
                'sites:read',
                'wordpress:sync'
            ),
            'metadata' => array(
                'source' => 'wordpress_plugin',
                'site_url' => $site_url,
                'wordpress_version' => get_bloginfo('version'),
                'plugin_version' => SILOQ_VERSION
            )
        );

        // Make API request to generate key
        $endpoint = "api-keys/generate";
        $result = $this->api_client->request('POST', $endpoint, $payload);

        if (is_wp_error($result)) {
            return $result;
        }

        // Store the API key securely
        $api_key = isset($result['key']) ? $result['key'] : '';
        if (empty($api_key)) {
            return new WP_Error('invalid_response', 'API key not returned from server');
        }

        // Encrypt and store the API key
        $encrypted_key = $this->encrypt_api_key($api_key);
        update_option(self::API_KEY_OPTION, $encrypted_key);

        // Store metadata
        $metadata = array(
            'key_id' => isset($result['id']) ? $result['id'] : '',
            'name' => isset($result['name']) ? $result['name'] : $name,
            'created_at' => isset($result['created_at']) ? $result['created_at'] : current_time('mysql'),
            'last_used_at' => null,
            'usage_count' => 0,
            'masked_key' => $this->mask_api_key($api_key)
        );
        update_option(self::API_KEY_META_OPTION, $metadata);

        return array(
            'key' => $api_key,
            'key_id' => $metadata['key_id'],
            'masked_key' => $metadata['masked_key'],
            'metadata' => $metadata
        );
    }

    /**
     * Validate an API key
     *
     * @param string $api_key API key to validate (optional, uses stored key if not provided)
     * @return bool|WP_Error True if valid, error otherwise
     */
    public function validate_api_key($api_key = null) {
        if (!$this->api_client) {
            return new WP_Error('no_api_client', 'API client not initialized');
        }

        // Use stored key if not provided
        if ($api_key === null) {
            $api_key = $this->get_api_key();
        }

        if (empty($api_key)) {
            return new WP_Error('no_api_key', 'No API key found');
        }

        // Make API request to validate
        $endpoint = "api-keys/validate";
        $payload = array('key' => $api_key);
        $result = $this->api_client->request('POST', $endpoint, $payload);

        if (is_wp_error($result)) {
            return $result;
        }

        // Update last used timestamp
        $this->update_usage_stats();

        return isset($result['valid']) ? $result['valid'] : true;
    }

    /**
     * Rotate API key (generate new and revoke old)
     *
     * @param string $reason Reason for rotation
     * @return array|WP_Error New API key data or error
     */
    public function rotate_api_key($reason = 'Manual rotation') {
        $metadata = get_option(self::API_KEY_META_OPTION, array());
        $old_key_id = isset($metadata['key_id']) ? $metadata['key_id'] : null;

        // Generate new key
        $new_key_result = $this->generate_api_key();

        if (is_wp_error($new_key_result)) {
            return $new_key_result;
        }

        // Revoke old key if it exists
        if ($old_key_id) {
            $this->revoke_api_key($old_key_id, $reason);
        }

        return $new_key_result;
    }

    /**
     * List all API keys for the site
     *
     * @return array|WP_Error List of API keys or error
     */
    public function list_api_keys() {
        if (!$this->api_client) {
            return new WP_Error('no_api_client', 'API client not initialized');
        }

        $site_id = get_option('siloq_site_id', '');
        if (empty($site_id)) {
            return new WP_Error('no_site_id', 'Site ID not configured');
        }

        $endpoint = "api-keys?site_id=" . $site_id;
        $result = $this->api_client->request('GET', $endpoint);

        if (is_wp_error($result)) {
            return $result;
        }

        return isset($result['keys']) ? $result['keys'] : array();
    }

    /**
     * Revoke an API key
     *
     * @param string $key_id API key ID to revoke
     * @param string $reason Reason for revocation
     * @return bool|WP_Error True if successful, error otherwise
     */
    public function revoke_api_key($key_id, $reason = 'Revoked by user') {
        if (!$this->api_client) {
            return new WP_Error('no_api_client', 'API client not initialized');
        }

        $endpoint = "api-keys/{$key_id}/revoke";
        $payload = array('reason' => $reason);
        $result = $this->api_client->request('POST', $endpoint, $payload);

        if (is_wp_error($result)) {
            return $result;
        }

        // Clear stored key if it matches
        $metadata = get_option(self::API_KEY_META_OPTION, array());
        if (isset($metadata['key_id']) && $metadata['key_id'] === $key_id) {
            delete_option(self::API_KEY_OPTION);
            delete_option(self::API_KEY_META_OPTION);
        }

        return true;
    }

    /**
     * Get the stored API key (decrypted)
     *
     * @return string Decrypted API key
     */
    public function get_api_key() {
        $encrypted_key = get_option(self::API_KEY_OPTION, '');
        if (empty($encrypted_key)) {
            return '';
        }

        return $this->decrypt_api_key($encrypted_key);
    }

    /**
     * Get API key metadata
     *
     * @return array API key metadata
     */
    public function get_api_key_metadata() {
        return get_option(self::API_KEY_META_OPTION, array());
    }

    /**
     * Update usage statistics
     *
     * @return void
     */
    private function update_usage_stats() {
        $metadata = get_option(self::API_KEY_META_OPTION, array());

        $metadata['last_used_at'] = current_time('mysql');
        $metadata['usage_count'] = isset($metadata['usage_count']) ? $metadata['usage_count'] + 1 : 1;

        update_option(self::API_KEY_META_OPTION, $metadata);
    }

    /**
     * Encrypt API key for storage
     *
     * @param string $api_key Plain API key
     * @return string Encrypted API key
     */
    private function encrypt_api_key($api_key) {
        // Use WordPress salt for encryption
        $salt = wp_salt('auth');
        $key = hash('sha256', $salt);
        $iv = substr(hash('sha256', $salt), 0, 16);

        $encrypted = openssl_encrypt($api_key, 'AES-256-CBC', $key, 0, $iv);
        return base64_encode($encrypted);
    }

    /**
     * Decrypt API key from storage
     *
     * @param string $encrypted_key Encrypted API key
     * @return string Decrypted API key
     */
    private function decrypt_api_key($encrypted_key) {
        $salt = wp_salt('auth');
        $key = hash('sha256', $salt);
        $iv = substr(hash('sha256', $salt), 0, 16);

        $encrypted = base64_decode($encrypted_key);
        return openssl_decrypt($encrypted, 'AES-256-CBC', $key, 0, $iv);
    }

    /**
     * Mask API key for display (show first 6 and last 4 characters)
     *
     * @param string $api_key Plain API key
     * @return string Masked API key
     */
    private function mask_api_key($api_key) {
        if (strlen($api_key) <= 10) {
            return str_repeat('*', strlen($api_key));
        }

        $prefix = substr($api_key, 0, 6);
        $suffix = substr($api_key, -4);
        $masked_length = strlen($api_key) - 10;

        return $prefix . str_repeat('*', $masked_length) . $suffix;
    }
}
