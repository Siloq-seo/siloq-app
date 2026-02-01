# Siloq Lead Gen Tool - Scoring Algorithm v1.1

## Philosophy

The score must reflect reality and create appropriate urgency. A site with keyword cannibalization issues should **never** receive an A-grade—that's the core problem we solve. The scoring system prioritizes cannibalization detection above all else because that's Siloq's unique value proposition.

**Key Principle:** We're not trying to scare people with fake bad scores. We're showing them the truth. Clean sites get good scores. Sites with real problems get scores that reflect it.

---

## Calculation Order (IMPORTANT)

**Step 1:** Start with 100 points

**Step 2:** Count and classify cannibalization conflicts

**Step 3:** Apply ALL deductions first (technical issues, content issues, etc.)

**Step 4:** Apply bonus points (max +15)

**Step 5:** THEN apply cannibalization cap (cap can only lower score, never raise it)

**Step 6:** Apply page count adjustment to cap (if applicable)

**Step 7:** Floor at 0, ceiling at 100

**Step 8:** Assign grade based on final score

```
Why this order matters:
- Deductions FIRST prevents backwards results
- A site with 5 conflicts and few other issues shouldn't score 
  higher than a site with 3 conflicts and many issues
- The cap is a ceiling, not a floor
```

---

## 1. Cannibalization Conflict Definitions

### What Counts as a Conflict

| Conflict Type | Severity Weight | Detection Method |
|---------------|-----------------|------------------|
| **Exact Match** | 1.5x | Two pages with identical primary keyword in title tag |
| **High Overlap** | 1.25x | >70% similarity in title tags OR H1s (use cosine similarity) |
| **Intent Collision** | 1.0x | Different keywords but same search intent (see detection below) |
| **URL Cannibalization** | 1.0x | Similar slugs targeting same topic (e.g., `/cheer-jackets/` vs `/jackets/cheer/`) |
| **Title Tag Duplicate** | 0.75x | Identical titles without other signals (may be false positive) |

### Same Intent Detection Signals

Apply "Same Intent" classification when **2 or more** of these match:

1. Title tag similarity >70% (cosine or Levenshtein)
2. H1 tag similarity >70%
3. URL slug contains the same primary keyword
4. Meta description similarity >60%
5. First paragraph content similarity >50%

### Conflict Counting

Each unique pair of conflicting pages = 1 conflict

Example: If pages A, B, and C all target "wedding photographer NYC":
- A↔B = 1 conflict
- A↔C = 1 conflict  
- B↔C = 1 conflict
- **Total: 3 conflicts**

Apply severity weight when calculating cap thresholds:
```
Weighted conflicts = Σ(conflict × severity weight)

Example:
- 1 Exact Match (1.5x) + 2 Intent Collisions (1.0x each)
- Weighted = 1.5 + 1.0 + 1.0 = 3.5 conflicts
- Use 3.5 to determine cap (rounds to nearest threshold)
```

---

## 2. Cannibalization Hard Caps

These caps set the MAXIMUM possible score. Applied AFTER deductions.

| Weighted Conflicts | Maximum Score | Maximum Grade |
|--------------------|---------------|---------------|
| 0                  | 100           | A+            |
| 0.5-1              | 84            | B             |
| 1.5-2              | 79            | C+            |
| 2.5-3              | 74            | C             |
| 3.5-4              | 69            | D+            |
| 4.5-6              | 64            | D             |
| 6.5-9              | 54            | D-            |
| 10+                | 44            | F             |

### Page Count Adjustment

Adjust the cap based on what percentage of pages are involved in conflicts:

| % of Pages in Conflicts | Cap Adjustment |
|-------------------------|----------------|
| >20%                    | No adjustment  |
| 10-20%                  | +5 to cap      |
| 5-10%                   | +10 to cap     |
| <5%                     | +15 to cap     |

```
Example:
- 500-page site with 3 conflicts (6 pages involved)
- 6/500 = 1.2% of pages
- Base cap for 3 conflicts = 74
- Adjustment for <5% = +15
- Adjusted cap = 89

This prevents large, generally healthy sites from being 
destroyed by a few conflicts.
```

---

## 3. Deduction Tables

### Content Issues

| Issue | Deduction | Notes |
|-------|-----------|-------|
| Missing H1 tag | -15 | Critical - basic SEO failure |
| Multiple H1 tags | -10 | Confuses hierarchy |
| Heading hierarchy skipped (H1→H3) | -12 | Breaks content structure |
| Title tag missing | -20 | Most critical on-page factor |
| Title tag too short (<30 chars) | -8 | |
| Title tag too long (>60 chars) | -5 | Less severe than too short |
| Meta description missing | -8 | |
| Meta description too short (<70 chars) | -4 | |
| Meta description too long (>160 chars) | -3 | |
| Duplicate title tags (per pair) | -12 | Strong cannibalization signal |
| Duplicate meta descriptions (per pair) | -6 | |
| Thin content (<300 words) | -8 | |
| Very thin content (<100 words) | -12 | |

### Technical SEO Issues

| Issue | Deduction | Notes |
|-------|-----------|-------|
| Sitemap not declared/missing | -8 | |
| Robots.txt missing | -5 | |
| No SSL/HTTPS | -15 | Security + ranking factor |
| Mixed content warnings | -10 | |
| Canonical tag missing | -10 | Cannibalization enabler |
| Canonical self-reference error | -8 | |
| Mobile viewport not set | -10 | Mobile-first indexing |
| Broken internal links (per link) | -5 | Max -20 total |
| 4xx/5xx errors on key pages | -10 | |

### Core Web Vitals

| Issue | Deduction | Notes |
|-------|-----------|-------|
| LCP > 2.5s | -8 | |
| LCP > 4.0s | -12 | Use this instead of above if >4s |
| CLS > 0.1 | -6 | |
| CLS > 0.25 | -10 | Use this instead of above if >0.25 |
| INP > 200ms | -6 | |
| INP > 500ms | -10 | Use this instead of above if >500ms |

### Structural Issues

| Issue | Deduction | Notes |
|-------|-----------|-------|
| No internal links (orphan page) | -10 | |
| Images missing alt tags (>50%) | -6 | |
| No schema markup | -3 | Nice to have |
| Broken breadcrumbs | -4 | |

---

## 4. Bonus Points (Max +15 Total)

| Achievement | Bonus |
|-------------|-------|
| All Core Web Vitals pass | +5 |
| Page speed <1.5s | +3 |
| Schema markup implemented correctly | +3 |
| Zero broken internal links | +2 |
| Proper heading hierarchy on all pages | +3 |
| All images have alt tags | +2 |

**Cap total bonuses at +15.** A perfect site with all bonuses can reach 100, but bonuses alone can't overcome real problems.

---

## 5. Same Intent Multiplier

When deductible issues occur on pages that are ALSO involved in cannibalization conflicts, apply **1.3x multiplier** to those specific deductions.

```
Example:
- Page A and Page B are cannibalizing each other
- Page A has missing H1 (-15)
- Page B has missing H1 (-15)
- Both deductions become: -15 × 1.3 = -19.5 each

Rationale: The damage compounds when cannibalizing pages 
BOTH have technical problems.
```

**Only apply to pages involved in conflicts, not site-wide issues.**

---

## 6. Grade Thresholds

| Score | Grade | Label | Hex Color |
|-------|-------|-------|-----------|
| 95-100 | A+ | Excellent | #22c55e |
| 90-94 | A | Great | #22c55e |
| 85-89 | B+ | Good | #84cc16 |
| 80-84 | B | Above Average | #84cc16 |
| 75-79 | C+ | Needs Improvement | #eab308 |
| 70-74 | C | Below Average | #eab308 |
| 65-69 | D+ | Poor | #f97316 |
| 60-64 | D | Serious Issues | #f97316 |
| 50-59 | D- | Critical Problems | #ef4444 |
| 0-49 | F | Failing | #dc2626 |

---

## 7. Category Breakdown (Diagnostic Display Only)

These are for the visual breakdown UI. They do NOT affect the main score calculation.

### Technical Score (100 points possible)
- Sitemap present: 15 pts
- Robots.txt present: 10 pts
- SSL/HTTPS: 20 pts
- Canonical tags correct: 20 pts
- Core Web Vitals pass: 20 pts
- Mobile-friendly: 15 pts

### Content Score (100 points possible)
- H1 tag present and singular: 25 pts
- Heading hierarchy correct: 20 pts
- Title tag optimized (30-60 chars): 25 pts
- Meta description optimized: 15 pts
- Content depth adequate: 15 pts

### Structure Score (100 points possible)
- Internal linking present: 25 pts
- No orphan pages: 25 pts
- Logical URL structure: 25 pts
- Navigation/breadcrumbs: 25 pts

### Performance Score (100 points possible)
- LCP < 2.5s: 35 pts
- CLS < 0.1: 25 pts
- INP < 200ms: 25 pts
- TTFB < 800ms: 15 pts

### SEO Score (100 points possible)
- Zero cannibalization: 50 pts (THIS IS BIG)
- Unique title tags: 15 pts
- Unique meta descriptions: 10 pts
- Proper canonical usage: 15 pts
- Schema markup: 10 pts

---

## 8. Quick Wins Output

After calculating the score, generate a prioritized list of 3-5 fixes:

### Priority Ranking Logic

| Issue Type | Priority Score |
|------------|----------------|
| Cannibalization conflict | 100 |
| Missing H1 | 80 |
| Title tag missing/broken | 75 |
| Canonical issues | 70 |
| Core Web Vitals failing | 60 |
| Heading hierarchy | 50 |
| Meta description issues | 40 |
| Other technical issues | 30 |

### Output Format

```json
{
  "quick_wins": [
    {
      "priority": 1,
      "issue": "Keyword Cannibalization",
      "description": "Pages /cheer-jackets/ and /jackets/cheer/ are competing for the same keyword",
      "recommendation": "Consolidate into single authoritative page or differentiate targeting",
      "impact": "High"
    },
    {
      "priority": 2,
      "issue": "Missing H1 Tag",
      "description": "Homepage has no H1 tag",
      "recommendation": "Add a single H1 tag containing primary keyword",
      "impact": "Medium"
    },
    {
      "priority": 3,
      "issue": "Title Tag Too Short",
      "description": "Homepage title is only 15 characters",
      "recommendation": "Expand to 30-60 characters with primary keyword",
      "impact": "Medium"
    }
  ]
}
```

---

## 9. Grade Messaging

| Grade | Headline | Body |
|-------|----------|------|
| A+/A | "Your site is well-optimized" | "Minor improvements available, but you're in great shape. Keep monitoring for new issues." |
| B+/B | "Good foundation with room to grow" | "Your site has solid fundamentals. Addressing the issues below will help you compete for top positions." |
| C+/C | "Several issues impacting performance" | "Your site has problems that are likely affecting your search visibility. The fixes below should be prioritized." |
| D+/D | "Significant problems detected" | "Your site has serious issues that are hurting your rankings. Immediate attention recommended." |
| D- | "Critical issues found" | "Your site is likely losing significant traffic due to these problems. These issues need to be addressed urgently." |
| F | "Severe problems require immediate action" | "Your site has fundamental issues, including keyword cannibalization, that are actively damaging your search visibility. Without fixes, rankings will continue to suffer." |

---

## 10. Example Calculations

### Example 1: crystallizedcouture.com

**Detected Issues:**
- 3 cannibalization conflicts (all Intent Collision type = 1.0x each)
- Missing H1 tag
- Heading hierarchy skipped (H1→H3)
- Title tag too short
- Sitemap not declared
- 1 page analyzed (single page site)

**Step 1:** Start with 100

**Step 2:** Weighted conflicts = 3 × 1.0 = 3.0

**Step 3:** Apply deductions
- Missing H1: -15
- Heading hierarchy: -12
- Title too short: -8
- Sitemap missing: -8
- Total deductions: -43
- Score after deductions: 100 - 43 = 57

**Step 4:** Bonuses: None detected = +0

**Step 5:** Apply cap
- 3 conflicts = cap at 74
- Current score (57) is below cap
- Score remains 57

**Step 6:** Page count adjustment
- 1 page, 3 conflicts = >20% involvement
- No adjustment

**Step 7:** Final score: 57

**Step 8:** Grade: D- (Critical Problems)

**Output:**
```
Score: 57
Grade: D-
Message: "Critical issues found. Your site is likely losing 
significant traffic due to these problems."
```

---

### Example 2: Clean Site with Minor Issues

**Detected Issues:**
- 0 cannibalization conflicts
- Meta description too long
- No schema markup

**Bonuses:**
- All CWV pass: +5
- Page speed <1.5s: +3
- Zero broken links: +2
- Proper heading hierarchy: +3

**Calculation:**
- Start: 100
- Deductions: -3 (meta) -3 (schema) = -6
- After deductions: 94
- Bonuses: +13 (capped at +15, so +13 is fine)
- After bonuses: 107 → capped at 100
- No cannibalization cap applies
- Final: 100

**Grade: A+ (Excellent)**

---

### Example 3: Large Site with Few Conflicts

**Site:** 500 pages, 2 conflicts (High Overlap type)

**Detected Issues:**
- 2 conflicts (1.25x each = 2.5 weighted)
- LCP > 4s
- CLS > 0.25
- Missing canonical on 3 pages
- Multiple H1s on homepage

**Calculation:**
- Start: 100
- Deductions: -12 (LCP) -10 (CLS) -30 (canonicals, 3×-10) -10 (H1s) = -62
- After deductions: 38
- Bonuses: None
- Cap for 2.5 conflicts: 79
- Current score (38) is below cap, stays 38
- Page count: 4 pages involved / 500 = 0.8% (<5%)
- Cap adjustment: +15 → adjusted cap = 94
- Score still 38 (cap doesn't help, only limits)
- Final: 38

**Grade: F (Failing)**

*Note: This site has serious technical problems beyond cannibalization. The few conflicts aren't the main issue here.*

---

### Example 4: Site with 1 Minor Conflict

**Site:** 20 pages, 1 Title Tag Duplicate conflict

**Detected Issues:**
- 1 conflict (Title Tag Duplicate = 0.75x = 0.75 weighted)
- Title tag too long on 2 pages

**Bonuses:**
- All CWV pass: +5
- Proper heading hierarchy: +3

**Calculation:**
- Start: 100
- Deductions: -10 (2 × -5 for title too long) = -10
- After deductions: 90
- Bonuses: +8
- After bonuses: 98
- Cap for 0.75 conflicts: 84
- Score (98) exceeds cap, reduced to 84
- Page count: 2/20 = 10%, adjustment +5 → cap = 89
- Final: 89

**Grade: B+ (Good)**

*This feels right. One minor conflict shouldn't destroy a score, but it does prevent an A.*

---

## 11. API Response Schema

```json
{
  "scan_id": "uuid",
  "url": "https://example.com",
  "scanned_at": "2025-01-31T17:30:00Z",
  "pages_analyzed": 1,
  "scan_time_seconds": 1.2,
  
  "score": {
    "final": 57,
    "grade": "D-",
    "label": "Critical Problems",
    "color": "#ef4444",
    "message": "Your site is likely losing significant traffic due to these problems."
  },
  
  "calculation_breakdown": {
    "starting_score": 100,
    "total_deductions": -43,
    "total_bonuses": 0,
    "score_before_cap": 57,
    "cannibalization_cap": 74,
    "page_count_adjustment": 0,
    "adjusted_cap": 74,
    "cap_applied": false
  },
  
  "cannibalization": {
    "conflict_count": 3,
    "weighted_conflict_count": 3.0,
    "conflicts": [
      {
        "type": "Intent Collision",
        "severity": 1.0,
        "page_a": "/services/",
        "page_b": "/what-we-do/",
        "signal_matches": ["title_similarity", "h1_similarity"]
      }
    ]
  },
  
  "categories": {
    "technical": { "score": 85, "max": 100 },
    "content": { "score": 45, "max": 100 },
    "structure": { "score": 100, "max": 100 },
    "performance": { "score": 100, "max": 100 },
    "seo": { "score": 50, "max": 100 }
  },
  
  "issues": [
    {
      "category": "content",
      "issue": "Missing H1 tag",
      "severity": "high",
      "deduction": -15,
      "url": "https://example.com/",
      "recommendation": "Add a single H1 tag containing primary keyword"
    }
  ],
  
  "bonuses": [],
  
  "quick_wins": [
    {
      "priority": 1,
      "issue": "Keyword Cannibalization",
      "description": "3 pages are competing for similar keywords",
      "recommendation": "Consolidate or differentiate page targeting",
      "impact": "High"
    }
  ]
}
```

---

## 12. Implementation Checklist

### MVP (Ship First)
- [ ] Basic conflict detection (title + H1 + URL similarity)
- [ ] Deduction calculations for all content/technical issues
- [ ] Hard caps based on conflict count
- [ ] Grade assignment
- [ ] Basic messaging
- [ ] Score display with breakdown

### V1.1 (Fast Follow)
- [ ] Conflict type classification with severity weights
- [ ] Page count adjustment
- [ ] Bonus points system
- [ ] Quick Wins prioritization
- [ ] Same Intent Multiplier
- [ ] Core Web Vitals integration

### V2 (Future)
- [ ] GSC integration for ranking-based severity
- [ ] Content freshness scoring
- [ ] Index coverage analysis
- [ ] Competitor comparison
- [ ] Historical tracking

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-31 | Initial algorithm |
| 1.1 | 2025-01-31 | Fixed cap math (deductions first), added conflict types, page count adjustment, bonus points, CWV, Quick Wins, API schema |

---

*Document Version: 1.1*
*Last Updated: January 31, 2025*
