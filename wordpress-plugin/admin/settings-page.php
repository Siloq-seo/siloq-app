<?php
/**
 * Siloq Settings Page
 * 
 * Admin settings page for configuring Siloq API connection
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Settings_Page {
    
    /**
     * Constructor
     */
    public function __construct() {
        add_action('admin_menu', array($this, 'add_admin_menu'));
        add_action('admin_init', array($this, 'register_settings'));
        add_action('admin_enqueue_scripts', array($this, 'enqueue_admin_scripts'));

        // AJAX handlers for API key management
        add_action('wp_ajax_siloq_generate_api_key', array($this, 'ajax_generate_api_key'));
        add_action('wp_ajax_siloq_rotate_api_key', array($this, 'ajax_rotate_api_key'));
        add_action('wp_ajax_siloq_generate_webhook_secret', array($this, 'ajax_generate_webhook_secret'));
    }
    
    /**
     * Add admin menu
     */
    public function add_admin_menu() {
        add_options_page(
            __('Siloq Settings', 'siloq-connector'),
            __('Siloq', 'siloq-connector'),
            'manage_options',
            'siloq-settings',
            array($this, 'render_settings_page')
        );
    }
    
    /**
     * Register settings
     */
    public function register_settings() {
        // API Configuration
        register_setting('siloq_settings', 'siloq_api_base_url', array(
            'type' => 'string',
            'sanitize_callback' => 'esc_url_raw',
            'default' => 'https://api.siloq.io/v1',
        ));
        
        register_setting('siloq_settings', 'siloq_api_key', array(
            'type' => 'string',
            'sanitize_callback' => 'sanitize_text_field',
        ));
        
        register_setting('siloq_settings', 'siloq_site_id', array(
            'type' => 'string',
            'sanitize_callback' => 'sanitize_text_field',
        ));
        
        // Sync Configuration
        register_setting('siloq_settings', 'siloq_sync_enabled', array(
            'type' => 'boolean',
            'default' => true,
        ));
        
        register_setting('siloq_settings', 'siloq_sync_post_types', array(
            'type' => 'array',
            'default' => array('page', 'post'),
        ));
        
        register_setting('siloq_settings', 'siloq_auto_sync', array(
            'type' => 'boolean',
            'default' => true,
        ));

        register_setting('siloq_settings', 'siloq_webhook_secret', array(
            'type' => 'string',
            'sanitize_callback' => 'sanitize_text_field',
        ));

        // Sections
        add_settings_section(
            'siloq_api_key_section',
            __('API Key Management', 'siloq-connector'),
            array($this, 'render_api_key_section_description'),
            'siloq-settings'
        );

        add_settings_section(
            'siloq_api_section',
            __('API Configuration', 'siloq-connector'),
            array($this, 'render_api_section_description'),
            'siloq-settings'
        );
        
        add_settings_section(
            'siloq_sync_section',
            __('Sync Configuration', 'siloq-connector'),
            array($this, 'render_sync_section_description'),
            'siloq-settings'
        );
        
        // API Key Management Fields
        add_settings_field(
            'siloq_api_key_display',
            __('Current API Key', 'siloq-connector'),
            array($this, 'render_api_key_display_field'),
            'siloq-settings',
            'siloq_api_key_section'
        );

        add_settings_field(
            'siloq_webhook_secret',
            __('Webhook Secret', 'siloq-connector'),
            array($this, 'render_webhook_secret_field'),
            'siloq-settings',
            'siloq_api_key_section'
        );

        // Fields
        add_settings_field(
            'siloq_api_base_url',
            __('API Base URL', 'siloq-connector'),
            array($this, 'render_api_base_url_field'),
            'siloq-settings',
            'siloq_api_section'
        );
        
        add_settings_field(
            'siloq_api_key',
            __('API Key', 'siloq-connector'),
            array($this, 'render_api_key_field'),
            'siloq-settings',
            'siloq_api_section'
        );
        
        add_settings_field(
            'siloq_site_id',
            __('Site ID', 'siloq-connector'),
            array($this, 'render_site_id_field'),
            'siloq-settings',
            'siloq_api_section'
        );
        
        add_settings_field(
            'siloq_sync_enabled',
            __('Enable Sync', 'siloq-connector'),
            array($this, 'render_sync_enabled_field'),
            'siloq-settings',
            'siloq_sync_section'
        );
        
        add_settings_field(
            'siloq_sync_post_types',
            __('Post Types to Sync', 'siloq-connector'),
            array($this, 'render_sync_post_types_field'),
            'siloq-settings',
            'siloq_sync_section'
        );
        
        add_settings_field(
            'siloq_auto_sync',
            __('Auto Sync on Publish', 'siloq-connector'),
            array($this, 'render_auto_sync_field'),
            'siloq-settings',
            'siloq_sync_section'
        );
    }
    
    /**
     * Render settings page
     */
    public function render_settings_page() {
        if (!current_user_can('manage_options')) {
            wp_die(__('You do not have sufficient permissions to access this page.'));
        }
        
        // Handle test connection
        if (isset($_POST['test_connection']) && check_admin_referer('siloq_test_connection')) {
            $this->handle_test_connection();
        }
        
        // Handle manual sync
        if (isset($_POST['manual_sync']) && check_admin_referer('siloq_manual_sync')) {
            $this->handle_manual_sync();
        }
        
        ?>
        <div class="wrap">
            <h1><?php echo esc_html(get_admin_page_title()); ?></h1>
            
            <form action="options.php" method="post">
                <?php
                settings_fields('siloq_settings');
                do_settings_sections('siloq-settings');
                submit_button(__('Save Settings', 'siloq-connector'));
                ?>
            </form>
            
            <hr>
            
            <h2><?php _e('Actions', 'siloq-connector'); ?></h2>
            
            <form method="post" action="">
                <?php wp_nonce_field('siloq_test_connection'); ?>
                <p>
                    <button type="submit" name="test_connection" class="button">
                        <?php _e('Test API Connection', 'siloq-connector'); ?>
                    </button>
                    <span class="description"><?php _e('Test your API connection settings', 'siloq-connector'); ?></span>
                </p>
            </form>
            
            <form method="post" action="">
                <?php wp_nonce_field('siloq_manual_sync'); ?>
                <p>
                    <button type="submit" name="manual_sync" class="button button-secondary">
                        <?php _e('Sync All Pages to Siloq', 'siloq-connector'); ?>
                    </button>
                    <span class="description"><?php _e('Manually sync all published pages to Siloq', 'siloq-connector'); ?></span>
                </p>
            </form>
        </div>
        <?php
    }
    
    /**
     * Render API key section description
     */
    public function render_api_key_section_description() {
        echo '<p>' . __('Manage your API key for secure communication with the Siloq platform. Generate a new API key or rotate your existing key for enhanced security.', 'siloq-connector') . '</p>';
    }

    /**
     * Render API section description
     */
    public function render_api_section_description() {
        echo '<p>' . __('Configure your Siloq API connection. You can find these settings in your Siloq dashboard.', 'siloq-connector') . '</p>';
    }
    
    /**
     * Render sync section description
     */
    public function render_sync_section_description() {
        echo '<p>' . __('Configure how WordPress content syncs with Siloq.', 'siloq-connector') . '</p>';
    }
    
    /**
     * Render API base URL field
     */
    public function render_api_base_url_field() {
        $value = get_option('siloq_api_base_url', 'https://api.siloq.io/v1');
        ?>
        <input type="url" name="siloq_api_base_url" value="<?php echo esc_attr($value); ?>" class="regular-text" />
        <p class="description"><?php _e('The base URL for the Siloq API', 'siloq-connector'); ?></p>
        <?php
    }
    
    /**
     * Render API key field
     */
    public function render_api_key_field() {
        $value = get_option('siloq_api_key', '');
        ?>
        <input type="password" name="siloq_api_key" value="<?php echo esc_attr($value); ?>" class="regular-text" />
        <p class="description"><?php _e('Your Siloq API key. This should be kept secure.', 'siloq-connector'); ?></p>
        <?php
    }
    
    /**
     * Render site ID field
     */
    public function render_site_id_field() {
        $value = get_option('siloq_site_id', '');
        ?>
        <input type="text" name="siloq_site_id" value="<?php echo esc_attr($value); ?>" class="regular-text" />
        <p class="description"><?php _e('Your Site ID in Siloq (UUID)', 'siloq-connector'); ?></p>
        <?php
    }
    
    /**
     * Render sync enabled field
     */
    public function render_sync_enabled_field() {
        $value = get_option('siloq_sync_enabled', true);
        ?>
        <label>
            <input type="checkbox" name="siloq_sync_enabled" value="1" <?php checked($value, true); ?> />
            <?php _e('Enable content synchronization with Siloq', 'siloq-connector'); ?>
        </label>
        <?php
    }
    
    /**
     * Render sync post types field
     */
    public function render_sync_post_types_field() {
        $value = get_option('siloq_sync_post_types', array('page', 'post'));
        $post_types = get_post_types(array('public' => true), 'objects');
        ?>
        <?php foreach ($post_types as $post_type): ?>
            <label style="display: block; margin-bottom: 5px;">
                <input type="checkbox" name="siloq_sync_post_types[]" value="<?php echo esc_attr($post_type->name); ?>"
                    <?php checked(in_array($post_type->name, $value)); ?> />
                <?php echo esc_html($post_type->label); ?>
            </label>
        <?php endforeach; ?>
        <p class="description"><?php _e('Select which post types should be synced to Siloq', 'siloq-connector'); ?></p>
        <?php
    }
    
    /**
     * Render auto sync field
     */
    public function render_auto_sync_field() {
        $value = get_option('siloq_auto_sync', true);
        ?>
        <label>
            <input type="checkbox" name="siloq_auto_sync" value="1" <?php checked($value, true); ?> />
            <?php _e('Automatically sync content when published', 'siloq-connector'); ?>
        </label>
        <?php
    }

    /**
     * Render API key display field
     */
    public function render_api_key_display_field() {
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-key-manager.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-client.php';

        $api_client = new Siloq_API_Client();
        $key_manager = new Siloq_API_Key_Manager($api_client);
        $metadata = $key_manager->get_api_key_metadata();

        ?>
        <div class="siloq-api-key-management">
            <?php if (!empty($metadata) && isset($metadata['masked_key'])): ?>
                <div class="siloq-api-key-display">
                    <code style="font-size: 14px; background: #f0f0f1; padding: 8px 12px; border-radius: 4px; display: inline-block;">
                        <?php echo esc_html($metadata['masked_key']); ?>
                    </code>

                    <?php if (isset($metadata['last_used_at']) && $metadata['last_used_at']): ?>
                        <p class="description">
                            <?php printf(
                                __('Last used: %s | Usage count: %d', 'siloq-connector'),
                                human_time_diff(strtotime($metadata['last_used_at'])) . ' ago',
                                isset($metadata['usage_count']) ? $metadata['usage_count'] : 0
                            ); ?>
                        </p>
                    <?php endif; ?>
                </div>

                <p>
                    <button type="button" id="siloq-rotate-api-key" class="button button-secondary">
                        <?php _e('Rotate API Key', 'siloq-connector'); ?>
                    </button>
                    <span class="description"><?php _e('Generate a new API key and revoke the current one', 'siloq-connector'); ?></span>
                </p>
            <?php else: ?>
                <p class="description"><?php _e('No API key configured.', 'siloq-connector'); ?></p>
                <p>
                    <button type="button" id="siloq-generate-api-key" class="button button-primary">
                        <?php _e('Generate API Key', 'siloq-connector'); ?>
                    </button>
                    <span class="description"><?php _e('Generate a new API key for this WordPress site', 'siloq-connector'); ?></span>
                </p>
            <?php endif; ?>

            <div id="siloq-api-key-message" style="margin-top: 10px;"></div>
        </div>
        <?php
    }

    /**
     * Render webhook secret field
     */
    public function render_webhook_secret_field() {
        $value = get_option('siloq_webhook_secret', '');
        $webhook_url = home_url('/siloq-webhook');
        ?>
        <div class="siloq-webhook-config">
            <input type="password" name="siloq_webhook_secret" id="siloq_webhook_secret" value="<?php echo esc_attr($value); ?>" class="regular-text" />
            <button type="button" id="siloq-generate-webhook-secret" class="button">
                <?php _e('Generate', 'siloq-connector'); ?>
            </button>
            <p class="description">
                <?php _e('Secret key for verifying webhook requests from Siloq. Keep this secure.', 'siloq-connector'); ?>
            </p>
            <p class="description">
                <strong><?php _e('Webhook URL:', 'siloq-connector'); ?></strong>
                <code><?php echo esc_html($webhook_url); ?></code>
                <button type="button" class="button button-small" onclick="navigator.clipboard.writeText('<?php echo esc_js($webhook_url); ?>')">
                    <?php _e('Copy', 'siloq-connector'); ?>
                </button>
            </p>
        </div>
        <?php
    }

    /**
     * Enqueue admin scripts
     */
    public function enqueue_admin_scripts($hook) {
        if ($hook !== 'settings_page_siloq-settings') {
            return;
        }

        wp_enqueue_script('siloq-admin', SILOQ_PLUGIN_URL . 'admin/js/admin.js', array('jquery'), SILOQ_VERSION, true);
        wp_enqueue_style('siloq-admin', SILOQ_PLUGIN_URL . 'admin/css/admin.css', array(), SILOQ_VERSION);

        // Localize script with nonces and AJAX URL
        wp_localize_script('siloq-admin', 'wp', array(
            'ajax_nonce' => wp_create_nonce('siloq_ajax'),
            'nonce_generate_api_key' => wp_create_nonce('siloq_generate_api_key'),
            'nonce_rotate_api_key' => wp_create_nonce('siloq_rotate_api_key'),
            'nonce_generate_webhook_secret' => wp_create_nonce('siloq_generate_webhook_secret'),
        ));
    }
    
    /**
     * Handle test connection
     */
    private function handle_test_connection() {
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-client.php';
        
        $api_client = new Siloq_API_Client();
        $result = $api_client->test_connection();
        
        if (is_wp_error($result)) {
            add_settings_error(
                'siloq_settings',
                'connection_error',
                __('Connection failed: ', 'siloq-connector') . $result->get_error_message(),
                'error'
            );
        } else {
            add_settings_error(
                'siloq_settings',
                'connection_success',
                __('Connection successful! Site: ', 'siloq-connector') . ($result['name'] ?? 'Connected'),
                'success'
            );
        }
        
        settings_errors('siloq_settings');
    }
    
    /**
     * Handle manual sync
     */
    private function handle_manual_sync() {
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-client.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-sync-engine.php';
        
        $api_client = new Siloq_API_Client();
        
        if (!$api_client->is_configured()) {
            add_settings_error(
                'siloq_settings',
                'sync_error',
                __('API is not configured. Please enter your API key and Site ID.', 'siloq-connector'),
                'error'
            );
            settings_errors('siloq_settings');
            return;
        }
        
        $sync_engine = new Siloq_Sync_Engine($api_client);
        $result = $sync_engine->sync_to_siloq('page', 100);
        
        add_settings_error(
            'siloq_settings',
            'sync_result',
            sprintf(
                __('Sync completed: %d of %d pages synced successfully.', 'siloq-connector'),
                $result['synced'],
                $result['total']
            ),
            $result['synced'] === $result['total'] ? 'success' : 'warning'
        );
        
        if (!empty($result['errors'])) {
            foreach ($result['errors'] as $error) {
                add_settings_error(
                    'siloq_settings',
                    'sync_error',
                    sprintf(
                        __('Error syncing "%s" (ID: %d): %s', 'siloq-connector'),
                        $error['title'],
                        $error['post_id'],
                        $error['error']
                    ),
                    'error'
                );
            }
        }
        
        settings_errors('siloq_settings');
    }

    /**
     * AJAX handler for generating API key
     */
    public function ajax_generate_api_key() {
        // Check permissions
        if (!current_user_can('manage_options')) {
            wp_send_json_error(array('message' => __('Insufficient permissions', 'siloq-connector')));
            return;
        }

        // Verify nonce
        if (!isset($_POST['nonce']) || !wp_verify_nonce($_POST['nonce'], 'siloq_generate_api_key')) {
            wp_send_json_error(array('message' => __('Invalid nonce', 'siloq-connector')));
            return;
        }

        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-client.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-key-manager.php';

        $api_client = new Siloq_API_Client();
        $key_manager = new Siloq_API_Key_Manager($api_client);

        $result = $key_manager->generate_api_key();

        if (is_wp_error($result)) {
            wp_send_json_error(array(
                'message' => $result->get_error_message(),
            ));
            return;
        }

        wp_send_json_success(array(
            'message' => __('API key generated successfully!', 'siloq-connector'),
            'masked_key' => $result['masked_key'],
            'metadata' => $result['metadata'],
        ));
    }

    /**
     * AJAX handler for rotating API key
     */
    public function ajax_rotate_api_key() {
        // Check permissions
        if (!current_user_can('manage_options')) {
            wp_send_json_error(array('message' => __('Insufficient permissions', 'siloq-connector')));
            return;
        }

        // Verify nonce
        if (!isset($_POST['nonce']) || !wp_verify_nonce($_POST['nonce'], 'siloq_rotate_api_key')) {
            wp_send_json_error(array('message' => __('Invalid nonce', 'siloq-connector')));
            return;
        }

        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-client.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-key-manager.php';

        $api_client = new Siloq_API_Client();
        $key_manager = new Siloq_API_Key_Manager($api_client);

        $reason = isset($_POST['reason']) ? sanitize_text_field($_POST['reason']) : 'Manual rotation via WordPress plugin';
        $result = $key_manager->rotate_api_key($reason);

        if (is_wp_error($result)) {
            wp_send_json_error(array(
                'message' => $result->get_error_message(),
            ));
            return;
        }

        wp_send_json_success(array(
            'message' => __('API key rotated successfully!', 'siloq-connector'),
            'masked_key' => $result['masked_key'],
            'metadata' => $result['metadata'],
        ));
    }

    /**
     * AJAX handler for generating webhook secret
     */
    public function ajax_generate_webhook_secret() {
        // Check permissions
        if (!current_user_can('manage_options')) {
            wp_send_json_error(array('message' => __('Insufficient permissions', 'siloq-connector')));
            return;
        }

        // Verify nonce
        if (!isset($_POST['nonce']) || !wp_verify_nonce($_POST['nonce'], 'siloq_generate_webhook_secret')) {
            wp_send_json_error(array('message' => __('Invalid nonce', 'siloq-connector')));
            return;
        }

        // Generate a secure random secret
        $secret = bin2hex(random_bytes(32));

        // Update option
        update_option('siloq_webhook_secret', $secret);

        wp_send_json_success(array(
            'message' => __('Webhook secret generated successfully!', 'siloq-connector'),
            'secret' => $secret,
        ));
    }
}

