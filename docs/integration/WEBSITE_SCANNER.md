# Website Scanner API

## Overview

The Siloq website scanner analyzes websites for SEO performance and provides actionable recommendations. It evaluates technical SEO, content quality, site structure, performance, and SEO-specific factors.

## API Endpoints

### Create Scan

**POST** `/api/v1/scans`

Start a new website scan. The scan runs in the background.

**Request Body:**
```json
{
  "url": "https://example.com",
  "scan_type": "full",
  "site_id": "optional-uuid"
}
```

**Parameters:**
- `url` (required): Website URL to scan (must be valid HTTP/HTTPS URL)
- `scan_type` (optional): Type of scan - `"full"`, `"quick"`, or `"technical"` (default: `"full"`)
- `site_id` (optional): UUID of existing site to link scan results

**Response:**
```json
{
  "id": "scan-uuid",
  "url": "https://example.com",
  "domain": "https://example.com",
  "scan_type": "full",
  "status": "pending",
  "overall_score": null,
  "grade": null,
  "technical_score": null,
  "content_score": null,
  "structure_score": null,
  "performance_score": null,
  "seo_score": null,
  "technical_details": {},
  "content_details": {},
  "structure_details": {},
  "performance_details": {},
  "seo_details": {},
  "recommendations": [],
  "pages_crawled": 0,
  "scan_duration_seconds": null,
  "error_message": null,
  "created_at": "2026-01-22T12:00:00Z",
  "completed_at": null
}
```

**Example:**
```bash
curl -X POST "https://api.siloq.ai/api/v1/scans" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "scan_type": "full"
  }'
```

### Get Scan Results

**GET** `/api/v1/scans/{scan_id}`

Retrieve scan results by ID. Use this to check scan status and get results.

**Response:**
Same structure as create scan, but with completed results when `status` is `"completed"`.

**Example:**
```bash
curl "https://api.siloq.ai/api/v1/scans/{scan_id}"
```

### List Scans

**GET** `/api/v1/scans`

List scans with optional filters.

**Query Parameters:**
- `domain` (optional): Filter by domain
- `site_id` (optional): Filter by site ID
- `status` (optional): Filter by status (`pending`, `processing`, `completed`, `failed`)
- `limit` (optional): Number of results (default: 20)
- `offset` (optional): Pagination offset (default: 0)

**Example:**
```bash
curl "https://api.siloq.ai/api/v1/scans?domain=https://example.com&status=completed&limit=10"
```

### Delete Scan

**DELETE** `/api/v1/scans/{scan_id}`

Delete a scan record.

**Example:**
```bash
curl -X DELETE "https://api.siloq.ai/api/v1/scans/{scan_id}"
```

## Scan Results

### Score Breakdown

Scans evaluate five categories:

1. **Technical SEO** (25% weight)
   - HTML5 doctype
   - Lang attribute
   - Charset declaration
   - Viewport meta tag
   - Canonical links
   - HTTPS usage
   - Robots.txt
   - Sitemap declaration
   - Favicon

2. **Content Quality** (20% weight)
   - Title tag (30-60 characters)
   - Meta description (120-160 characters)
   - H1 tag (exactly one)
   - Heading structure hierarchy
   - Image alt text coverage
   - Content length (minimum 300 words)

3. **Site Structure** (20% weight)
   - Navigation structure
   - Footer presence
   - Structured data (JSON-LD schema)
   - Internal linking

4. **Performance** (20% weight)
   - Response time (< 3 seconds)
   - Page size (< 2MB)
   - Compression (gzip/brotli)

5. **SEO Factors** (15% weight)
   - Open Graph tags
   - Twitter Card tags
   - Robots meta tags (noindex check)

### Overall Score & Grade

The overall score is a weighted average of all category scores:
- **A+**: 97-100
- **A**: 93-96
- **B+**: 87-92
- **B**: 83-86
- **C+**: 77-82
- **C**: 73-76
- **D+**: 67-72
- **D**: 63-66
- **F**: 0-62

### Recommendations

Each scan includes up to 10 actionable recommendations prioritized by:
- **High**: Critical issues (HTTPS, title tags, noindex)
- **Medium**: Important improvements (meta descriptions, alt text, schema)

## Scan Status

- `pending`: Scan queued, not started
- `processing`: Scan in progress
- `completed`: Scan finished successfully
- `failed`: Scan encountered an error

## Usage Example

```python
import httpx

# Create scan
response = httpx.post(
    "https://api.siloq.ai/api/v1/scans",
    json={"url": "https://example.com", "scan_type": "full"}
)
scan = response.json()
scan_id = scan["id"]

# Poll for results
import time
while True:
    response = httpx.get(f"https://api.siloq.ai/api/v1/scans/{scan_id}")
    result = response.json()
    
    if result["status"] == "completed":
        print(f"Score: {result['overall_score']} ({result['grade']})")
        for rec in result["recommendations"]:
            print(f"- {rec['category']}: {rec['issue']}")
        break
    elif result["status"] == "failed":
        print(f"Scan failed: {result['error_message']}")
        break
    
    time.sleep(2)  # Poll every 2 seconds
```

## Integration with scan.siloq.ai

The scanner is designed to be used by the `scan.siloq.ai` landing page:

1. User enters website URL
2. Frontend calls `POST /api/v1/scans`
3. Frontend polls `GET /api/v1/scans/{scan_id}` until status is `completed`
4. Display results with scores, grade, and recommendations

## Database Schema

Scans are stored in the `scans` table (see `migrations/V014__website_scanner.sql`):

- Links to `sites` table (optional)
- Stores all scores and detailed findings
- Tracks scan execution metadata
- Indexed for fast queries by domain, site_id, status, and score

## Future Enhancements

- Multi-page crawling (currently scans homepage only)
- Historical tracking (compare scans over time)
- Scheduled scans
- Email notifications when scans complete
- Export reports (PDF, CSV)
- Comparison tool (compare multiple sites)
