# WordPress TALI (Theme-Aware Layout Intelligence) Implementation

## Overview

TALI solves the **Last-Mile Design Gap** for non-technical WordPress site owners by fingerprinting the active WordPress theme's design tokens and injecting Siloq-generated content as theme-native Gutenberg blocks.

## Implementation Status

### ✅ Completed Components

#### 1. WordPress Plugin TALI Classes

**File**: `wordpress-plugin/includes/`

- ✅ **class-siloq-tali-fingerprinter.php**: Theme design token extraction
  - Extracts colors, typography, spacing, and layout tokens from `theme.json`
  - Falls back to CSS variables for classic themes
  - Syncs design profile to Siloq API
  
- ✅ **class-siloq-tali-component-discovery.php**: Component capability detection
  - Discovers supported Gutenberg blocks (buttons, grids, accordions, etc.)
  - Calculates confidence scores for each component
  - Stores capability map in WordPress options
  
- ✅ **class-siloq-tali-block-injector.php**: Authority block injection
  - Creates Gutenberg blocks with claim anchors
  - Generates deterministic claim IDs (format: `CLAIM:TYPE-HASH`)
  - Wraps content in authority containers with required attributes
  - Includes semantic HTML with Schema.org microdata for FAQs
  
- ✅ **class-siloq-tali-access-control.php**: Access state enforcement
  - Checks claim state via Siloq API (ENABLED/FROZEN)
  - Filters post content to enforce access states
  - Preserves receipts even when content is frozen
  
- ✅ **class-siloq-tali-confidence-gate.php**: Confidence thresholds and fail-safes
  - Validates layout confidence before injection
  - Creates drafts if confidence < 0.90
  - Validates semantic readiness, wrapper requirements, and claim anchors
  - Shows admin notices for low confidence scenarios

#### 2. FastAPI Endpoints

**File**: `app/api/routes/wordpress.py`

- ✅ **POST /api/v1/wordpress/projects/{project_id}/theme-profile**
  - Syncs WordPress theme design profile to Siloq
  - Stores theme tokens and metadata
  - Logs theme profile sync events
  
- ✅ **GET /api/v1/wordpress/claims/{claim_id}/state**
  - Returns access state for claim ID (ENABLED or FROZEN)
  - Used by WordPress access control to determine content rendering
  
- ✅ **POST /api/v1/wordpress/projects/{project_id}/pages/sync**
  - Syncs WordPress pages to Siloq
  - Creates or updates Siloq page records
  - Stores WordPress post ID mappings
  
- ✅ **POST /api/v1/wordpress/projects/{project_id}/pages/{page_id}/inject-blocks**
  - Prepares authority blocks for injection
  - Generates claim manifest
  - Returns block injection data for WordPress plugin

#### 3. Plugin Integration

**File**: `wordpress-plugin/siloq-connector.php`

- ✅ **TALI components loaded on plugin init**
- ✅ **Theme fingerprinting on activation**
- ✅ **Component discovery on activation**
- ✅ **Theme change detection** (re-fingerprints on theme switch)
- ✅ **Admin menu for TALI management**
- ✅ **Content filtering** for access state enforcement
- ✅ **API client methods** for TALI operations

## Design Profile Structure

```json
{
  "tali_version": "1.0",
  "platform": "wordpress",
  "theme": {
    "name": "Twenty Twenty-Four",
    "stylesheet": "twentytwentyfour",
    "is_block_theme": true,
    "template": "single",
    "version": "1.0"
  },
  "tokens": {
    "colors": {
      "primary": "var(--wp--preset--color--primary)",
      "secondary": "var(--wp--preset--color--secondary)",
      "text": "var(--wp--preset--color--foreground)",
      "background": "var(--wp--preset--color--background)"
    },
    "typography": {
      "font_family": "var(--wp--preset--font-family--system-font)",
      "h1": { "size": "...", "weight": "700", "line_height": "1.2" },
      "h2": { "size": "...", "weight": "600", "line_height": "1.3" },
      "body": { "size": "...", "weight": "400", "line_height": "1.6" }
    },
    "spacing": {
      "xs": "var(--wp--preset--spacing--20)",
      "sm": "var(--wp--preset--spacing--30)",
      "md": "var(--wp--preset--spacing--40)"
    },
    "layout": {
      "content_width": "var(--wp--style--global--content-size)",
      "wide_width": "var(--wp--style--global--wide-size)"
    }
  },
  "fingerprinted_at": "2026-01-09T12:00:00Z"
}
```

## Capability Map Structure

```json
{
  "supports": {
    "cta_buttons": true,
    "grid_layout": true,
    "accordion_faq": false,
    "tables": true,
    "testimonials": false,
    "image_gallery": true,
    "columns": true,
    "group": true
  },
  "confidence": {
    "cta_buttons": 0.95,
    "grid_layout": 0.9,
    "accordion_faq": 0.3,
    "tables": 1.0,
    "testimonials": 0.0,
    "image_gallery": 0.85,
    "columns": 0.95,
    "group": 1.0
  }
}
```

## Authority Block Structure

Every injected authority unit includes:

1. **Authority Container Wrapper**:
   ```html
   <div class="siloq-authority-container"
        data-siloq-claim-id="CLAIM:SRV-104-A"
        data-siloq-governance="V1"
        data-siloq-template="service_city"
        data-siloq-theme="twentytwentyfour">
   ```

2. **Authority Receipt Comment**:
   ```html
   <!-- SiloqAuthorityReceipt: CLAIM:SRV-104-A -->
   ```

3. **Semantic Content** (SSR-required):
   - Headings (`<h1>`, `<h2>`, etc.)
   - Paragraphs (`<p>`)
   - Lists (`<ul>`, `<ol>`)
   - FAQ sections with Schema.org microdata
   - CTA buttons

## Access State Enforcement

- **ENABLED**: Full content rendered with authority wrapper
- **FROZEN**: Content suppressed, receipt preserved:
  ```html
  <div class="siloq-authority-container" 
       data-siloq-claim-id="CLAIM:SRV-104-A"
       data-siloq-access="FROZEN">
    <!-- SiloqAuthorityReceipt: CLAIM:SRV-104-A -->
    <!-- SiloqNotice: Authority preserved; rendering suppressed due to access state -->
  </div>
  ```

## Confidence Gate Rules

- **Threshold**: 0.90 (90% confidence required)
- **Failure Actions**:
  - Page created as draft (not published)
  - Admin notice shown with confidence score
  - Missing components listed
  - User must manually review before publishing

## Fail-Safe Rules

TALI NEVER auto-publishes content that fails:

1. ✅ Semantic readiness (content exists in HTML source)
2. ✅ Wrapper requirements (claim anchors present)
3. ✅ Access-state enforcement (frozen check passed)
4. ✅ Claim-anchor presence (receipt comment exists)
5. ✅ Confidence threshold (≥ 0.90)

## Usage Flow

### 1. Plugin Activation

```php
// On activation:
$tali_fingerprinter = new Siloq_TALI_Fingerprinter($api_client);
$tali_fingerprinter->fingerprint_theme();

$tali_discovery = new Siloq_TALI_Component_Discovery();
$tali_discovery->discover_capabilities();
```

### 2. Content Injection

```php
// When Siloq generates content:
$block_injector = new Siloq_TALI_Block_Injector($api_client);
$gutenberg_blocks = $block_injector->inject_authority_blocks(
    $page_id,
    $content_data,
    $claim_manifest
);

// Save to WordPress post
wp_update_post(array(
    'ID' => $page_id,
    'post_content' => $gutenberg_blocks
));
```

### 3. Access State Check (Runtime)

```php
// Content is filtered automatically via 'the_content' filter
// Access control checks claim state and renders accordingly
$access_control = new Siloq_TALI_Access_Control($api_client);
// Filter is automatically applied on init
```

### 4. Confidence Validation

```php
// Before publishing:
$confidence_gate = new Siloq_TALI_Confidence_Gate();
$validation = $confidence_gate->validate_before_publish(
    $page_id,
    $content,
    $template
);

if (!$validation['valid']) {
    // Page remains draft, admin notice shown
}
```

## API Integration

### WordPress → Siloq

1. **Theme Profile Sync**: `POST /api/v1/wordpress/projects/{project_id}/theme-profile`
2. **Page Sync**: `POST /api/v1/wordpress/projects/{project_id}/pages/sync`
3. **Claim State Check**: `GET /api/v1/wordpress/claims/{claim_id}/state`

### Siloq → WordPress

1. **Block Injection Data**: `POST /api/v1/wordpress/projects/{project_id}/pages/{page_id}/inject-blocks`

## TALI Laws (Non-Negotiable)

1. ✅ **NO_EXTERNAL_FRAMEWORKS**: Never inject external CSS/JS frameworks
2. ✅ **SERVER_SOURCE_AUTHORITY**: Core content must exist in HTML source (SSR)
3. ✅ **NO_NET_NEW_DATA**: TALI structures approved content; never invents facts
4. ✅ **THEME_RESPECT**: Adapt to theme tokens; do not impose design system
5. ✅ **FAIL_SAFE**: If confidence < 0.90, create as Draft + require review

## Testing Checklist

- [ ] Theme fingerprinting works on activation
- [ ] Component discovery detects supported blocks
- [ ] Authority blocks inject with claim anchors
- [ ] Frozen state suppresses content but preserves receipts
- [ ] Semantic HTML exists in page source
- [ ] Draft fallback occurs when confidence < 0.90
- [ ] No external CSS/JS frameworks injected
- [ ] Theme tokens extracted from theme.json
- [ ] Plugin can connect to Siloq API via API key
- [ ] Access state enforcement works correctly
- [ ] Confidence gate prevents publishing low-confidence layouts

## Next Steps

1. **Claim Registry**: Create database table for claim-to-project mapping
2. **Enhanced Fingerprinting**: Use headless browser to extract computed CSS values
3. **Block Style Matching**: Automatically match injected blocks to theme styles
4. **Pattern Library**: Build library of authority block templates per template type
5. **Preview Mode**: Allow preview of injected blocks before publishing

## Notes

- All authority content **MUST** exist in HTML source (no JS-only rendering)
- Claim receipts **MUST** be preserved even when content is frozen
- Confidence thresholds are **ENFORCED** - no exceptions
- Theme fingerprinting runs on activation, theme change, and manual trigger
- Access states are checked **PER REQUEST** (not cached indefinitely)
