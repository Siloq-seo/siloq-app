# Siloq WordPress Connector

A lightweight WordPress plugin that connects your WordPress site to the Siloq SEO platform. This plugin implements the CMS Adapter Pattern, allowing WordPress to communicate with Siloq's Decision Engine, Restoration Engine, and Agent services.

## Architecture

This plugin follows a **separate SaaS platform + WordPress plugin** architecture:

- **Siloq Platform**: Standalone web application hosting all business logic
- **WordPress Plugin**: Lightweight connector that communicates via REST API

The plugin does **NOT** contain business logic - it's a secure tunnel between WordPress and Siloq.

## Features

### Phase 1 (v1) - Current Implementation

- ✅ **API Authentication**: Secure connection to Siloq platform
- ✅ **One-way Sync**: WordPress → Siloq (audit mode)
- ✅ **Manual Content Import**: Import generated content from Siloq → WordPress
- ✅ **JSON-LD Schema Injection**: Automatically injects schema into page head
- ✅ **Basic Redirect Handling**: Manages redirects from Siloq governance decisions
- ✅ **Admin Settings Page**: Configure API connection

### Phase 2 (v2) - Planned

- Bidirectional sync
- Real-time content updates
- Internal link injection
- Image optimization sync
- Automated Agent actions (with approval)

### Phase 3 (v3) - Future

- Full Agent autonomy (if enabled)
- Gutenberg block integration
- Visual silo builder in WP admin
- Real-time validation in editor

## Installation

### Requirements

- WordPress 5.8 or higher
- PHP 7.4 or higher
- cURL extension enabled

### Manual Installation

1. Download or clone this repository
2. Upload the `wordpress-plugin` folder to `/wp-content/plugins/`
3. Rename the folder to `siloq-connector`
4. Activate the plugin through the 'Plugins' menu in WordPress

### Configuration

1. Go to **Settings → Siloq** in WordPress admin
2. Enter your **API Base URL** (default: `https://api.siloq.io/v1`)
3. Enter your **API Key** (found in your Siloq dashboard)
4. Enter your **Site ID** (UUID from your Siloq dashboard)
5. Click **Save Settings**
6. Click **Test API Connection** to verify your settings

## Usage

### Automatic Sync

When **Auto Sync on Publish** is enabled (default), the plugin automatically syncs published pages and posts to Siloq when they are saved.

### Manual Sync

1. Go to **Settings → Siloq**
2. Click **Sync All Pages to Siloq**
3. The plugin will sync all published pages

### Sync Individual Page

The plugin adds a "Sync to Siloq" action to the post/page edit screen (via custom action hook).

### Receiving Content from Siloq

Content updates from Siloq are received via webhook. Configure your webhook URL in Siloq:

```
https://yoursite.com/siloq-webhook
```

**Webhook Security**: Set a webhook secret in `siloq_webhook_secret` option to verify webhook signatures.

### Supported Webhook Events

- `content.updated` - Content has been generated/updated
- `schema.updated` - JSON-LD schema has been updated
- `redirect.created` - Redirect has been created
- `links.updated` - Internal links have been updated
- `page.published` - Page has been published in Siloq

## API Endpoints Used

The plugin communicates with the following Siloq API endpoints:

### Pages

- `POST /pages` - Create page
- `GET /pages/{page_id}` - Get page details
- `PUT /pages/{page_id}` - Update page
- `POST /pages/{page_id}/validate` - Validate page before generation
- `POST /pages/{page_id}/publish` - Publish page
- `GET /pages/{page_id}/jsonld` - Get JSON-LD schema
- `GET /pages/{page_id}/gates` - Check publish gates

### Jobs

- `GET /jobs/{job_id}` - Get job status
- `POST /jobs/{job_id}/transition` - Transition job state

### Sites

- `GET /sites/{site_id}` - Get site details (used for connection test)

## Database Tables

The plugin creates two database tables:

### `wp_siloq_redirects`

Stores redirect rules from Siloq governance decisions.

| Column | Type | Description |
|--------|------|-------------|
| id | bigint | Primary key |
| source_url | varchar(255) | Source URL to redirect from |
| target_url | varchar(255) | Target URL to redirect to |
| redirect_type | int | HTTP redirect code (301, 302, etc.) |
| created_at | datetime | When redirect was created |

### `wp_siloq_page_mappings`

Maps WordPress posts to Siloq pages.

| Column | Type | Description |
|--------|------|-------------|
| id | bigint | Primary key |
| wp_post_id | bigint | WordPress post ID |
| siloq_page_id | varchar(36) | Siloq page UUID |
| synced_at | datetime | Last sync timestamp |

## Post Meta Fields

The plugin uses the following WordPress post meta fields:

- `siloq_jsonld_schema` - JSON-LD schema for the page
- `siloq_internal_links` - Internal links to inject into content
- `siloq_faq_items` - FAQ items for FAQ schema
- `siloq_last_synced` - Last sync timestamp
- `siloq_sync_status` - Sync status (success, error, etc.)
- `siloq_content_received_at` - When content was received from Siloq
- `siloq_published_at` - When page was published in Siloq
- `siloq_custom_prompt` - Custom prompt for content generation

## Hooks and Filters

### Actions

- `siloq_post_synced` - Fired after a post is synced to Siloq
  ```php
  do_action('siloq_post_synced', $wp_post_id, $siloq_page_id, $result);
  ```

- `siloq_content_received` - Fired when content is received from Siloq
  ```php
  do_action('siloq_content_received', $wp_post_id, $payload);
  ```

### Filters

- `siloq_sync_post_types` - Filter which post types to sync
  ```php
  add_filter('siloq_sync_post_types', function($post_types) {
      return array('page', 'post', 'custom_post_type');
  });
  ```

- `siloq_api_request_args` - Filter API request arguments
  ```php
  add_filter('siloq_api_request_args', function($args, $method, $endpoint) {
      // Modify request arguments
      return $args;
  }, 10, 3);
  ```

## Security

- API keys are stored securely in WordPress options
- Webhook signatures can be verified using HMAC
- All API requests use HTTPS
- User permissions are checked before sync operations

## Troubleshooting

### Connection Test Fails

1. Verify your API key is correct
2. Check that Site ID is a valid UUID
3. Ensure API Base URL is correct
4. Check if your server can make outbound HTTPS requests

### Content Not Syncing

1. Check "Enable Sync" is enabled in settings
2. Verify the post type is included in "Post Types to Sync"
3. Check WordPress error logs for API errors
4. Ensure post is published (drafts are not synced)

### Webhooks Not Working

1. Verify webhook URL is accessible: `https://yoursite.com/siloq-webhook`
2. Check webhook secret matches in both systems
3. Check WordPress error logs for webhook errors
4. Verify rewrite rules are flushed (go to Settings → Permalinks and click Save)

## Development

### File Structure

```
wordpress-plugin/
├── siloq-connector.php          # Main plugin file
├── includes/
│   ├── class-siloq-api-client.php      # API communication
│   ├── class-siloq-sync-engine.php     # Content sync
│   ├── class-siloq-redirect-manager.php # Redirect management
│   └── class-siloq-schema-injector.php  # Schema injection
├── admin/
│   └── settings-page.php        # Admin settings page
└── webhooks/
    └── content-receiver.php     # Webhook receiver
```

### Testing

1. Enable WordPress debug mode: `define('WP_DEBUG', true);`
2. Check error logs for API communication issues
3. Use browser developer tools to inspect API requests

## Support

For support, issues, or feature requests, please contact Siloq support or open an issue in the repository.

## License

GPL v2 or later

## Changelog

### 1.0.0
- Initial release
- API authentication
- One-way sync (WordPress → Siloq)
- JSON-LD schema injection
- Redirect management
- Admin settings page
- Webhook receiver

