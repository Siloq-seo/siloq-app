<?php
/**
 * Siloq Permissions Manager
 *
 * Handles role-based access control (RBAC) for Siloq operations
 */

if (!defined('ABSPATH')) {
    exit;
}

class Siloq_Permissions {

    /**
     * Custom capabilities
     */
    const CAP_SYNC = 'siloq_sync';
    const CAP_GENERATE = 'siloq_generate';
    const CAP_MANAGE_KEYS = 'siloq_manage_keys';
    const CAP_VIEW_LOGS = 'siloq_view_logs';
    const CAP_MANAGE_SETTINGS = 'siloq_manage_settings';

    /**
     * Register custom capabilities on plugin activation
     */
    public static function register_capabilities() {
        // Get roles
        $admin = get_role('administrator');
        $editor = get_role('editor');

        // Administrator gets all capabilities
        if ($admin) {
            $admin->add_cap(self::CAP_SYNC);
            $admin->add_cap(self::CAP_GENERATE);
            $admin->add_cap(self::CAP_MANAGE_KEYS);
            $admin->add_cap(self::CAP_VIEW_LOGS);
            $admin->add_cap(self::CAP_MANAGE_SETTINGS);
        }

        // Editor gets sync and generate capabilities
        if ($editor) {
            $editor->add_cap(self::CAP_SYNC);
            $editor->add_cap(self::CAP_GENERATE);
            $editor->add_cap(self::CAP_VIEW_LOGS);
        }
    }

    /**
     * Remove custom capabilities on plugin deactivation
     */
    public static function remove_capabilities() {
        // Get all roles
        $roles = array('administrator', 'editor', 'author', 'contributor');

        foreach ($roles as $role_name) {
            $role = get_role($role_name);
            if ($role) {
                $role->remove_cap(self::CAP_SYNC);
                $role->remove_cap(self::CAP_GENERATE);
                $role->remove_cap(self::CAP_MANAGE_KEYS);
                $role->remove_cap(self::CAP_VIEW_LOGS);
                $role->remove_cap(self::CAP_MANAGE_SETTINGS);
            }
        }
    }

    /**
     * Check if current user can sync content
     *
     * @param int $user_id Optional user ID (defaults to current user)
     * @return bool True if user can sync
     */
    public function user_can_sync($user_id = null) {
        if ($user_id === null) {
            return current_user_can(self::CAP_SYNC);
        }

        $user = get_user_by('id', $user_id);
        return $user && $user->has_cap(self::CAP_SYNC);
    }

    /**
     * Check if current user can generate content
     *
     * @param int $user_id Optional user ID (defaults to current user)
     * @return bool True if user can generate
     */
    public function user_can_generate($user_id = null) {
        if ($user_id === null) {
            return current_user_can(self::CAP_GENERATE);
        }

        $user = get_user_by('id', $user_id);
        return $user && $user->has_cap(self::CAP_GENERATE);
    }

    /**
     * Check if current user can manage API keys
     *
     * @param int $user_id Optional user ID (defaults to current user)
     * @return bool True if user can manage keys
     */
    public function user_can_manage_keys($user_id = null) {
        if ($user_id === null) {
            return current_user_can(self::CAP_MANAGE_KEYS);
        }

        $user = get_user_by('id', $user_id);
        return $user && $user->has_cap(self::CAP_MANAGE_KEYS);
    }

    /**
     * Check if current user can view logs
     *
     * @param int $user_id Optional user ID (defaults to current user)
     * @return bool True if user can view logs
     */
    public function user_can_view_logs($user_id = null) {
        if ($user_id === null) {
            return current_user_can(self::CAP_VIEW_LOGS);
        }

        $user = get_user_by('id', $user_id);
        return $user && $user->has_cap(self::CAP_VIEW_LOGS);
    }

    /**
     * Check if current user can manage settings
     *
     * @param int $user_id Optional user ID (defaults to current user)
     * @return bool True if user can manage settings
     */
    public function user_can_manage_settings($user_id = null) {
        if ($user_id === null) {
            return current_user_can(self::CAP_MANAGE_SETTINGS);
        }

        $user = get_user_by('id', $user_id);
        return $user && $user->has_cap(self::CAP_MANAGE_SETTINGS);
    }

    /**
     * Check if current user can access dashboard
     *
     * @return bool True if user can access dashboard
     */
    public function user_can_access_dashboard() {
        return $this->user_can_sync() || $this->user_can_view_logs();
    }

    /**
     * Get user's Siloq capabilities
     *
     * @param int $user_id Optional user ID (defaults to current user)
     * @return array Array of capabilities
     */
    public function get_user_capabilities($user_id = null) {
        if ($user_id === null) {
            $user_id = get_current_user_id();
        }

        if (!$user_id) {
            return array();
        }

        $capabilities = array();
        $all_caps = array(
            self::CAP_SYNC,
            self::CAP_GENERATE,
            self::CAP_MANAGE_KEYS,
            self::CAP_VIEW_LOGS,
            self::CAP_MANAGE_SETTINGS,
        );

        foreach ($all_caps as $cap) {
            if (user_can($user_id, $cap)) {
                $capabilities[] = $cap;
            }
        }

        return $capabilities;
    }

    /**
     * Grant capability to user
     *
     * @param int $user_id User ID
     * @param string $capability Capability to grant
     * @return bool True on success
     */
    public function grant_capability($user_id, $capability) {
        $user = get_user_by('id', $user_id);

        if (!$user) {
            return false;
        }

        // Verify it's a valid Siloq capability
        $valid_caps = array(
            self::CAP_SYNC,
            self::CAP_GENERATE,
            self::CAP_MANAGE_KEYS,
            self::CAP_VIEW_LOGS,
            self::CAP_MANAGE_SETTINGS,
        );

        if (!in_array($capability, $valid_caps)) {
            return false;
        }

        $user->add_cap($capability);
        return true;
    }

    /**
     * Revoke capability from user
     *
     * @param int $user_id User ID
     * @param string $capability Capability to revoke
     * @return bool True on success
     */
    public function revoke_capability($user_id, $capability) {
        $user = get_user_by('id', $user_id);

        if (!$user) {
            return false;
        }

        $user->remove_cap($capability);
        return true;
    }

    /**
     * Check permission before AJAX action
     *
     * @param string $action Action being performed
     * @return bool|WP_Error True if allowed, WP_Error if not
     */
    public function check_ajax_permission($action) {
        $permission_map = array(
            'siloq_sync_now' => self::CAP_SYNC,
            'siloq_generate_content' => self::CAP_GENERATE,
            'siloq_generate_api_key' => self::CAP_MANAGE_KEYS,
            'siloq_rotate_api_key' => self::CAP_MANAGE_KEYS,
            'siloq_check_gates' => self::CAP_SYNC,
            'siloq_poll_job_status' => self::CAP_GENERATE,
        );

        if (!isset($permission_map[$action])) {
            // No specific permission required, check if user is logged in
            return is_user_logged_in() ? true : new WP_Error('not_logged_in', 'You must be logged in');
        }

        $required_cap = $permission_map[$action];

        if (!current_user_can($required_cap)) {
            return new WP_Error(
                'insufficient_permissions',
                sprintf('You need the %s capability to perform this action', $required_cap)
            );
        }

        return true;
    }

    /**
     * Get permission requirements for admin pages
     *
     * @return array Permission requirements
     */
    public function get_page_permissions() {
        return array(
            'siloq-settings' => self::CAP_MANAGE_SETTINGS,
            'siloq-dashboard' => self::CAP_VIEW_LOGS,
            'siloq-tali' => 'manage_options',
        );
    }

    /**
     * Check if user can access admin page
     *
     * @param string $page Page slug
     * @return bool True if user can access
     */
    public function user_can_access_page($page) {
        $page_permissions = $this->get_page_permissions();

        if (!isset($page_permissions[$page])) {
            return current_user_can('edit_posts');
        }

        return current_user_can($page_permissions[$page]);
    }

    /**
     * Log permission check
     *
     * @param string $action Action being checked
     * @param bool $allowed Whether permission was granted
     * @param int $user_id User ID
     */
    private function log_permission_check($action, $allowed, $user_id = null) {
        if ($user_id === null) {
            $user_id = get_current_user_id();
        }

        if (!apply_filters('siloq_log_permission_checks', false)) {
            return;
        }

        error_log(sprintf(
            'Siloq Permission Check: User %d %s to perform action: %s',
            $user_id,
            $allowed ? 'allowed' : 'denied',
            $action
        ));
    }

    /**
     * Get all users with Siloq capabilities
     *
     * @return array Array of WP_User objects
     */
    public function get_users_with_capabilities() {
        $users = array();

        // Get all users who can sync (this covers most Siloq users)
        $sync_users = get_users(array(
            'capability' => self::CAP_SYNC,
        ));

        foreach ($sync_users as $user) {
            $users[$user->ID] = $user;
        }

        // Also get users who can manage keys (admins)
        $admin_users = get_users(array(
            'capability' => self::CAP_MANAGE_KEYS,
        ));

        foreach ($admin_users as $user) {
            $users[$user->ID] = $user;
        }

        return array_values($users);
    }

    /**
     * Display capability information
     *
     * @return string HTML output
     */
    public function render_capability_info() {
        ob_start();
        ?>
        <div class="siloq-capability-info">
            <h3><?php _e('Siloq Capabilities', 'siloq-connector'); ?></h3>
            <ul>
                <li><strong><?php echo esc_html(self::CAP_SYNC); ?>:</strong> <?php _e('Ability to sync content with Siloq', 'siloq-connector'); ?></li>
                <li><strong><?php echo esc_html(self::CAP_GENERATE); ?>:</strong> <?php _e('Ability to generate content using AI', 'siloq-connector'); ?></li>
                <li><strong><?php echo esc_html(self::CAP_MANAGE_KEYS); ?>:</strong> <?php _e('Ability to manage API keys', 'siloq-connector'); ?></li>
                <li><strong><?php echo esc_html(self::CAP_VIEW_LOGS); ?>:</strong> <?php _e('Ability to view sync logs and errors', 'siloq-connector'); ?></li>
                <li><strong><?php echo esc_html(self::CAP_MANAGE_SETTINGS); ?>:</strong> <?php _e('Ability to manage plugin settings', 'siloq-connector'); ?></li>
            </ul>
        </div>
        <?php
        return ob_get_clean();
    }
}
