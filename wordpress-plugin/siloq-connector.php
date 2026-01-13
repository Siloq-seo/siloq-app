<?php
/**
 * Plugin Name: Siloq Connector
 * Plugin URI: https://siloq.io
 * Description: Connects WordPress to Siloq SEO platform for automated content governance and optimization.
 * Version: 1.0.0
 * Author: Siloq
 * Author URI: https://siloq.io
 * License: GPL v2 or later
 * License URI: https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain: siloq-connector
 * Domain Path: /languages
 * Requires at least: 5.8
 * Requires PHP: 7.4
 */

// Exit if accessed directly
if (!defined('ABSPATH')) {
    exit;
}

// Define plugin constants
define('SILOQ_VERSION', '1.0.0');
define('SILOQ_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('SILOQ_PLUGIN_URL', plugin_dir_url(__FILE__));
define('SILOQ_PLUGIN_BASENAME', plugin_basename(__FILE__));

/**
 * Main plugin class
 */
class Siloq_Connector {
    
    /**
     * Instance of this class
     */
    private static $instance = null;
    
    /**
     * API client instance
     */
    private $api_client = null;
    
    /**
     * Sync engine instance
     */
    private $sync_engine = null;
    
    /**
     * Redirect manager instance
     */
    private $redirect_manager = null;
    
    /**
     * Get singleton instance
     */
    public static function get_instance() {
        if (null === self::$instance) {
            self::$instance = new self();
        }
        return self::$instance;
    }
    
    /**
     * Constructor
     */
    private function __construct() {
        $this->init_hooks();
        $this->load_dependencies();
    }
    
    /**
     * Initialize WordPress hooks
     */
    private function init_hooks() {
        // Activation/Deactivation hooks
        register_activation_hook(__FILE__, array($this, 'activate'));
        register_deactivation_hook(__FILE__, array($this, 'deactivate'));
        
        // Load plugin text domain
        add_action('plugins_loaded', array($this, 'load_textdomain'));
        
        // Initialize admin
        if (is_admin()) {
            require_once SILOQ_PLUGIN_DIR . 'admin/settings-page.php';
            new Siloq_Settings_Page();
        }
        
        // Initialize webhook receiver
        add_action('init', array($this, 'init_webhooks'));
        
        // Content sync hooks
        add_action('save_post', array($this, 'sync_post_to_siloq'), 10, 2);
        add_action('wp_loaded', array($this, 'init_sync_engine'));
        
        // Schema injection
        add_action('wp_head', array($this, 'inject_jsonld_schema'));
        
        // Redirect management
        add_action('template_redirect', array($this, 'handle_redirects'));
        
        // Internal link injection
        add_filter('the_content', array($this, 'inject_internal_links'), 20);
        
        // TALI access control for content filtering
        $tali_access_control = new Siloq_TALI_Access_Control($this->api_client);
        add_filter('the_content', array($tali_access_control, 'filter_post_content'), 30);
        
        // TALI fingerprint on theme change
        add_action('switch_theme', array($this, 'on_theme_change'));
        
        // Add admin menu for TALI
        if (is_admin()) {
            add_action('admin_menu', array($this, 'add_tali_admin_menu'));
        }
    }
    
    /**
     * Handle theme change - re-fingerprint
     */
    public function on_theme_change() {
        if ($this->api_client && $this->api_client->is_configured()) {
            $tali_fingerprinter = new Siloq_TALI_Fingerprinter($this->api_client);
            $tali_fingerprinter->fingerprint_theme();
            
            // Re-discover component capabilities
            $tali_discovery = new Siloq_TALI_Component_Discovery();
            $tali_discovery->discover_capabilities();
        }
    }
    
    /**
     * Add TALI admin menu
     */
    public function add_tali_admin_menu() {
        add_submenu_page(
            'tools.php',
            __('Siloq TALI', 'siloq-connector'),
            __('Siloq TALI', 'siloq-connector'),
            'manage_options',
            'siloq-tali',
            array($this, 'render_tali_admin_page')
        );
    }
    
    /**
     * Render TALI admin page
     */
    public function render_tali_admin_page() {
        // Get current theme profile and capability map
        $design_profile = get_option('siloq_design_profile', array());
        $capability_map = get_option('siloq_component_capability_map', array());
        
        // Handle re-fingerprint action
        if (isset($_POST['re_fingerprint']) && check_admin_referer('siloq_re_fingerprint')) {
            $tali_fingerprinter = new Siloq_TALI_Fingerprinter($this->api_client);
            $design_profile = $tali_fingerprinter->fingerprint_theme();
            
            $tali_discovery = new Siloq_TALI_Component_Discovery();
            $capability_map = $tali_discovery->discover_capabilities();
            
            echo '<div class="notice notice-success"><p>Theme re-fingerprinted successfully!</p></div>';
        }
        
        ?>
        <div class="wrap">
            <h1><?php echo esc_html__('Siloq TALI (Theme-Aware Layout Intelligence)', 'siloq-connector'); ?></h1>
            
            <div class="card">
                <h2><?php echo esc_html__('Theme Design Profile', 'siloq-connector'); ?></h2>
                <?php if (!empty($design_profile)): ?>
                    <p><strong>Theme:</strong> <?php echo esc_html($design_profile['theme']['name'] ?? 'Unknown'); ?></p>
                    <p><strong>Fingerprinted:</strong> <?php echo esc_html($design_profile['fingerprinted_at'] ?? 'Never'); ?></p>
                    <details>
                        <summary>View Full Profile</summary>
                        <pre><?php echo esc_html(json_encode($design_profile, JSON_PRETTY_PRINT)); ?></pre>
                    </details>
                <?php else: ?>
                    <p><?php echo esc_html__('No theme profile found. Run fingerprint to generate one.', 'siloq-connector'); ?></p>
                <?php endif; ?>
            </div>
            
            <div class="card">
                <h2><?php echo esc_html__('Component Capability Map', 'siloq-connector'); ?></h2>
                <?php if (!empty($capability_map)): ?>
                    <table class="wp-list-table widefat fixed striped">
                        <thead>
                            <tr>
                                <th>Component</th>
                                <th>Supported</th>
                                <th>Confidence</th>
                            </tr>
                        </thead>
                        <tbody>
                            <?php foreach ($capability_map['supports'] ?? array() as $component => $supported): ?>
                                <tr>
                                    <td><?php echo esc_html($component); ?></td>
                                    <td><?php echo $supported ? '✓' : '✗'; ?></td>
                                    <td><?php echo isset($capability_map['confidence'][$component]) ? number_format($capability_map['confidence'][$component] * 100, 1) . '%' : 'N/A'; ?></td>
                                </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                <?php else: ?>
                    <p><?php echo esc_html__('No capability map found. Run component discovery to generate one.', 'siloq-connector'); ?></p>
                <?php endif; ?>
            </div>
            
            <form method="post" action="">
                <?php wp_nonce_field('siloq_re_fingerprint'); ?>
                <button type="submit" name="re_fingerprint" class="button button-primary">
                    <?php echo esc_html__('Re-Fingerprint Theme', 'siloq-connector'); ?>
                </button>
            </form>
        </div>
        <?php
    }
    
    /**
     * Load plugin dependencies
     */
    private function load_dependencies() {
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-api-client.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-sync-engine.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-redirect-manager.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-schema-injector.php';
        
        // TALI components
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-tali-fingerprinter.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-tali-component-discovery.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-tali-block-injector.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-tali-access-control.php';
        require_once SILOQ_PLUGIN_DIR . 'includes/class-siloq-tali-confidence-gate.php';
        
        $this->api_client = new Siloq_API_Client();
        $this->sync_engine = new Siloq_Sync_Engine($this->api_client);
        $this->redirect_manager = new Siloq_Redirect_Manager();
    }
    
    /**
     * Plugin activation
     */
    public function activate() {
        // Create database tables
        $this->create_tables();
        
        // Set default options
        if (!get_option('siloq_api_base_url')) {
            update_option('siloq_api_base_url', 'https://api.siloq.io/v1');
        }
        
        // Run TALI fingerprint on activation
        if ($this->api_client && $this->api_client->is_configured()) {
            $tali_fingerprinter = new Siloq_TALI_Fingerprinter($this->api_client);
            $tali_fingerprinter->fingerprint_theme();
            
            // Also discover component capabilities
            $tali_discovery = new Siloq_TALI_Component_Discovery();
            $tali_discovery->discover_capabilities();
        }
        
        // Flush rewrite rules for webhooks
        flush_rewrite_rules();
    }
    
    /**
     * Plugin deactivation
     */
    public function deactivate() {
        // Clear scheduled events
        wp_clear_scheduled_hook('siloq_sync_to_platform');
        
        // Flush rewrite rules
        flush_rewrite_rules();
    }
    
    /**
     * Create database tables
     */
    private function create_tables() {
        global $wpdb;
        
        $charset_collate = $wpdb->get_charset_collate();
        
        // Redirects table
        $table_redirects = $wpdb->prefix . 'siloq_redirects';
        $sql_redirects = "CREATE TABLE IF NOT EXISTS $table_redirects (
            id bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
            source_url varchar(255) NOT NULL,
            target_url varchar(255) NOT NULL,
            redirect_type int(11) NOT NULL DEFAULT 301,
            created_at datetime DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY source_url (source_url(191))
        ) $charset_collate;";
        
        // Page mappings table
        $table_mappings = $wpdb->prefix . 'siloq_page_mappings';
        $sql_mappings = "CREATE TABLE IF NOT EXISTS $table_mappings (
            id bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
            wp_post_id bigint(20) UNSIGNED NOT NULL,
            siloq_page_id varchar(36) NOT NULL,
            synced_at datetime DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY wp_post_id (wp_post_id),
            KEY siloq_page_id (siloq_page_id(36))
        ) $charset_collate;";
        
        require_once(ABSPATH . 'wp-admin/includes/upgrade.php');
        dbDelta($sql_redirects);
        dbDelta($sql_mappings);
    }
    
    /**
     * Load plugin text domain
     */
    public function load_textdomain() {
        load_plugin_textdomain(
            'siloq-connector',
            false,
            dirname(SILOQ_PLUGIN_BASENAME) . '/languages'
        );
    }
    
    /**
     * Initialize webhook receiver
     */
    public function init_webhooks() {
        // Register webhook endpoint
        add_rewrite_rule(
            '^siloq-webhook/?$',
            'index.php?siloq_webhook=1',
            'top'
        );
        
        add_filter('query_vars', function($vars) {
            $vars[] = 'siloq_webhook';
            return $vars;
        });
        
        add_action('template_redirect', function() {
            if (get_query_var('siloq_webhook')) {
                require_once SILOQ_PLUGIN_DIR . 'webhooks/content-receiver.php';
                exit;
            }
        });
    }
    
    /**
     * Sync post to Siloq when saved
     */
    public function sync_post_to_siloq($post_id, $post) {
        // Skip autosaves and revisions
        if (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) {
            return;
        }
        
        if (wp_is_post_revision($post_id)) {
            return;
        }
        
        // Only sync published pages/posts
        if ($post->post_status !== 'publish') {
            return;
        }
        
        // Only sync specific post types (default: page, post)
        $allowed_types = apply_filters('siloq_sync_post_types', array('page', 'post'));
        if (!in_array($post->post_type, $allowed_types)) {
            return;
        }
        
        // Check if sync is enabled
        if (!get_option('siloq_sync_enabled', true)) {
            return;
        }
        
        // Schedule sync (async)
        wp_schedule_single_event(time() + 5, 'siloq_sync_post', array($post_id));
    }
    
    /**
     * Initialize sync engine
     */
    public function init_sync_engine() {
        if (!$this->sync_engine) {
            return;
        }
        
        // Hook into scheduled sync event
        add_action('siloq_sync_post', array($this->sync_engine, 'sync_single_post'));
        
        // Manual sync action
        add_action('wp_ajax_siloq_sync_page', array($this->sync_engine, 'ajax_sync_page'));
    }
    
    /**
     * Inject JSON-LD schema into head
     */
    public function inject_jsonld_schema() {
        if (!is_singular()) {
            return;
        }
        
        global $post;
        $schema = get_post_meta($post->ID, 'siloq_jsonld_schema', true);
        
        if ($schema) {
            if (is_string($schema)) {
                $schema = json_decode($schema, true);
            }
            
            if (is_array($schema) && !empty($schema)) {
                echo '<script type="application/ld+json">' . "\n";
                echo wp_json_encode($schema, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
                echo "\n" . '</script>' . "\n";
            }
        }
    }
    
    /**
     * Handle redirects
     */
    public function handle_redirects() {
        if (!$this->redirect_manager) {
            return;
        }
        
        $current_url = $_SERVER['REQUEST_URI'];
        $redirect = $this->redirect_manager->get_redirect($current_url);
        
        if ($redirect) {
            wp_redirect($redirect['target_url'], $redirect['redirect_type']);
            exit;
        }
    }
    
    /**
     * Inject internal links into content
     */
    public function inject_internal_links($content) {
        if (!is_singular()) {
            return $content;
        }
        
        global $post;
        $links = get_post_meta($post->ID, 'siloq_internal_links', true);
        
        if (!$links || !is_array($links)) {
            return $content;
        }
        
        foreach ($links as $link) {
            if (!isset($link['anchor_text']) || !isset($link['target_url']) || !isset($link['position'])) {
                continue;
            }
            
            $anchor = '<a href="' . esc_url($link['target_url']) . '">' . esc_html($link['anchor_text']) . '</a>';
            
            // Insert at specified position
            if ($link['position'] === 'end') {
                $content .= ' ' . $anchor;
            } elseif ($link['position'] === 'after_paragraph' && isset($link['paragraph_index'])) {
                $paragraphs = explode('</p>', $content);
                if (isset($paragraphs[$link['paragraph_index']])) {
                    $paragraphs[$link['paragraph_index']] .= ' ' . $anchor;
                    $content = implode('</p>', $paragraphs);
                }
            }
        }
        
        return $content;
    }
    
    /**
     * Get API client instance
     */
    public function get_api_client() {
        return $this->api_client;
    }
    
    /**
     * Get sync engine instance
     */
    public function get_sync_engine() {
        return $this->sync_engine;
    }
}

/**
 * Initialize plugin
 */
function siloq_connector_init() {
    return Siloq_Connector::get_instance();
}

// Start the plugin
siloq_connector_init();

