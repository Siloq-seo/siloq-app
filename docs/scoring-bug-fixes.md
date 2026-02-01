# Scoring Algorithm - Bug Fixes Required

**Reviewed by:** Arc (AI)  
**Date:** January 31, 2026

The JS implementation is solid but has these issues to fix before shipping:

---

## 🐛 Bugs to Fix

### 1. Cannibalization Caps Table Missing Entry

**File:** `src/scoring/siloq-scoring-algorithm.js`  
**Line:** ~15 (CONFIG.cannibalizationCaps)

**Problem:** Table jumps from 4 to 6, missing entry for 5 conflicts.

**Current:**
```javascript
cannibalizationCaps: [
  [0, 100],
  [1, 84],
  [2, 79],
  [3, 74],
  [4, 69],
  [6, 64],  // ← Jumps from 4 to 6
  [9, 54],
  [Infinity, 44]
]
```

**Fix:**
```javascript
cannibalizationCaps: [
  [0, 100],
  [1, 84],
  [2, 79],
  [3, 74],
  [4, 69],
  [5, 64],  // ← Add this
  [6, 64],
  [9, 54],
  [Infinity, 44]
]
```

---

### 2. maxTotal Logic is Backwards

**File:** `src/scoring/siloq-scoring-algorithm.js`  
**Line:** ~185 (inside calculateScore, deduction loop)

**Problem:** `maxTotal` values are negative (e.g., -20), so the comparison logic is inverted.

**Current (buggy):**
```javascript
if (deductionDef.maxTotal) {
  const key = issue.type;
  deductionTracker[key] = (deductionTracker[key] || 0) + points;
  if (deductionTracker[key] < deductionDef.maxTotal) {  // ← Wrong comparison
    points = 0;
  }
  // ...
}
```

**Fix:**
```javascript
if (deductionDef.maxTotal) {
  const key = issue.type;
  const currentTotal = deductionTracker[key] || 0;
  const newTotal = currentTotal + points;
  
  if (currentTotal <= deductionDef.maxTotal) {
    // Already at max, no more deductions
    points = 0;
  } else if (newTotal < deductionDef.maxTotal) {
    // Would exceed max, cap it
    points = deductionDef.maxTotal - currentTotal;
  }
  
  deductionTracker[key] = currentTotal + points;
}
```

---

### 3. Grade Thresholds Need F Split

**File:** `src/scoring/siloq-scoring-algorithm.js`  
**Line:** ~55 (CONFIG.gradeThresholds)

**Problem:** Per spec, 40-49 should be "F" and 0-39 should be "F (Severe)".

**Current:**
```javascript
gradeThresholds: [
  // ...
  [50, 'D-', 'Critical Problems', '#ef4444'],
  [0, 'F', 'Failing', '#dc2626']  // Only one F tier
]
```

**Fix:**
```javascript
gradeThresholds: [
  // ...
  [50, 'D-', 'Critical Problems', '#ef4444'],
  [40, 'F', 'Failing', '#ef4444'],
  [0, 'F', 'Severe - Immediate Action', '#dc2626']
]
```

**Also add second F message:**
```javascript
gradeMessages: {
  // ... existing messages
  'F': 'Severe problems require immediate action. Cannibalization is actively damaging your search visibility.',
}
```

Note: The grade lookup will need to handle the F/Severe distinction based on score (0-39 vs 40-49).

---

### 4. SEO Category Score Doesn't Reflect Cannibalization

**File:** `src/scoring/siloq-scoring-algorithm.js`  
**Line:** ~380 (calculateCategoryScores function)

**Problem:** Per spec, SEO category should have 50 points for "zero cannibalization". Current implementation doesn't penalize conflicts.

**Fix:** Update `calculateCategoryScores` to accept conflicts:

```javascript
function calculateCategoryScores(deductions, bonuses, conflicts) {
  const categories = {
    technical: { score: 100, max: 100 },
    content: { score: 100, max: 100 },
    structure: { score: 100, max: 100 },
    performance: { score: 100, max: 100 },
    seo: { score: 100, max: 100 }
  };

  // Apply deductions to categories
  deductions.forEach(ded => {
    if (categories[ded.category]) {
      categories[ded.category].score += ded.points;
    }
  });

  // SEO category: penalize for cannibalization (50 points at stake)
  if (conflicts.length > 0) {
    const conflictPenalty = Math.min(50, conflicts.length * 15);
    categories.seo.score -= conflictPenalty;
  }

  // Floor at 0
  Object.keys(categories).forEach(key => {
    categories[key].score = Math.max(0, categories[key].score);
  });

  return categories;
}
```

Update the call site (~line 245):
```javascript
const categoryScores = calculateCategoryScores(appliedDeductions, appliedBonuses, conflicts);
```

---

### 5. Missing Duplicate Detection Function

**Problem:** The spec mentions detecting duplicate title tags and meta descriptions across pages, but `processScan()` doesn't call a duplicate detection function.

**Add new function:**
```javascript
function detectDuplicates(pages) {
  const issues = [];
  const titles = new Map();
  const metas = new Map();
  
  pages.forEach(page => {
    // Track titles
    if (page.title) {
      if (titles.has(page.title)) {
        issues.push({ 
          type: 'duplicate_title', 
          url: page.url, 
          duplicateOf: titles.get(page.title) 
        });
      } else {
        titles.set(page.title, page.url);
      }
    }
    
    // Track meta descriptions
    if (page.metaDescription && page.metaDescription.length > 20) {
      if (metas.has(page.metaDescription)) {
        issues.push({ 
          type: 'duplicate_meta', 
          url: page.url, 
          duplicateOf: metas.get(page.metaDescription) 
        });
      } else {
        metas.set(page.metaDescription, page.url);
      }
    }
  });
  
  return issues;
}
```

**Update `processScan()` (~line 475):**
```javascript
function processScan(crawlResult) {
  const { url, pages, siteData, scanTime } = crawlResult;

  let allIssues = [];
  pages.forEach(page => {
    const pageIssues = detectIssues(page);
    allIssues = allIssues.concat(pageIssues);
  });

  // Add site-wide issues
  const siteIssues = detectSiteIssues(siteData);
  allIssues = allIssues.concat(siteIssues);

  // Add duplicate detection
  const duplicateIssues = detectDuplicates(pages);
  allIssues = allIssues.concat(duplicateIssues);

  // ... rest of function
}
```

**Add to exports:**
```javascript
module.exports = {
  // ... existing exports
  detectDuplicates,
};
```

---

## 🧪 Additional Test Cases Needed

Add these tests to `siloq-scoring-tests.js`:

### Test 6: Same Intent Multiplier
Verify 1.3x multiplier applies to issues on conflicting pages.

### Test 7: Bonus Cap
Verify bonuses cap at +15 even if more are earned.

### Test 8: Conflict Type Weighting  
Verify exact_match (1.5x) results in lower cap than title_duplicate (0.75x).

### Test 9: Score Floor
Verify score never goes negative even with massive deductions.

### Test 10: Schema Validation
Verify API response contains all required fields.

---

## ✅ After Fixes

Run the test file:
```bash
node src/scoring/siloq-scoring-tests.js
```

All tests should pass. If Test 1 (crystallizedcouture) scores > 60, something is still wrong.

---

*— Arc*
