/**
 * Siloq Lead Gen Scoring Algorithm v1.1
 * 
 * Usage:
 *   const result = calculateScore(scanData);
 *   console.log(result.score.final); // 57
 *   console.log(result.score.grade); // "D-"
 */

// =============================================================================
// CONFIGURATION - Adjust these values as needed
// =============================================================================

const CONFIG = {
  // Cannibalization caps: [maxConflicts, capScore]
  cannibalizationCaps: [
    [0, 100],
    [1, 84],
    [2, 79],
    [3, 74],
    [4, 69],
    [6, 64],
    [9, 54],
    [Infinity, 44]
  ],

  // Conflict type severity weights
  conflictSeverity: {
    'exact_match': 1.5,
    'high_overlap': 1.25,
    'intent_collision': 1.0,
    'url_cannibalization': 1.0,
    'title_duplicate': 0.75
  },

  // Page count adjustments: [maxPercentage, capAdjustment]
  pageCountAdjustments: [
    [5, 15],   // <5% of pages involved = +15 to cap
    [10, 10],  // 5-10% = +10
    [20, 5],   // 10-20% = +5
    [Infinity, 0] // >20% = no adjustment
  ],

  // Same intent multiplier for issues on conflicting pages
  sameIntentMultiplier: 1.3,

  // Maximum bonus points allowed
  maxBonusPoints: 15,

  // Grade thresholds: [minScore, grade, label, color]
  gradeThresholds: [
    [95, 'A+', 'Excellent', '#22c55e'],
    [90, 'A', 'Great', '#22c55e'],
    [85, 'B+', 'Good', '#84cc16'],
    [80, 'B', 'Above Average', '#84cc16'],
    [75, 'C+', 'Needs Improvement', '#eab308'],
    [70, 'C', 'Below Average', '#eab308'],
    [65, 'D+', 'Poor', '#f97316'],
    [60, 'D', 'Serious Issues', '#f97316'],
    [50, 'D-', 'Critical Problems', '#ef4444'],
    [0, 'F', 'Failing', '#dc2626']
  ],

  // Grade messages
  gradeMessages: {
    'A+': 'Your site is well-optimized. Minor improvements available, but you\'re in great shape.',
    'A': 'Your site is well-optimized. Minor improvements available, but you\'re in great shape.',
    'B+': 'Good foundation with room to grow. Addressing the issues below will help you compete for top positions.',
    'B': 'Good foundation with room to grow. Addressing the issues below will help you compete for top positions.',
    'C+': 'Several issues are impacting your search performance. The fixes below should be prioritized.',
    'C': 'Several issues are impacting your search performance. The fixes below should be prioritized.',
    'D+': 'Significant problems detected that are hurting your rankings. Immediate attention recommended.',
    'D': 'Significant problems detected that are hurting your rankings. Immediate attention recommended.',
    'D-': 'Critical issues found. Your site is likely losing significant traffic due to these problems.',
    'F': 'Severe problems require immediate action. Cannibalization is actively damaging your search visibility.'
  }
};

// =============================================================================
// DEDUCTION DEFINITIONS
// =============================================================================

const DEDUCTIONS = {
  // Content Issues
  missing_h1: { points: -15, category: 'content', severity: 'high', recommendation: 'Add a single H1 tag containing your primary keyword' },
  multiple_h1: { points: -10, category: 'content', severity: 'medium', recommendation: 'Ensure exactly one H1 tag per page' },
  heading_hierarchy_skipped: { points: -12, category: 'content', severity: 'high', recommendation: 'Fix heading hierarchy (H1 → H2 → H3, no skipping)' },
  title_missing: { points: -20, category: 'content', severity: 'critical', recommendation: 'Add a title tag with primary keyword' },
  title_too_short: { points: -8, category: 'content', severity: 'medium', recommendation: 'Expand title tag to 30-60 characters with primary keyword' },
  title_too_long: { points: -5, category: 'content', severity: 'low', recommendation: 'Shorten title tag to under 60 characters' },
  meta_description_missing: { points: -8, category: 'content', severity: 'medium', recommendation: 'Add a compelling meta description (70-160 characters)' },
  meta_description_too_short: { points: -4, category: 'content', severity: 'low', recommendation: 'Expand meta description to at least 70 characters' },
  meta_description_too_long: { points: -3, category: 'content', severity: 'low', recommendation: 'Shorten meta description to under 160 characters' },
  duplicate_title: { points: -12, category: 'content', severity: 'high', recommendation: 'Create unique title tags for each page' },
  duplicate_meta: { points: -6, category: 'content', severity: 'medium', recommendation: 'Create unique meta descriptions for each page' },
  thin_content: { points: -8, category: 'content', severity: 'medium', recommendation: 'Expand content to at least 300 words' },
  very_thin_content: { points: -12, category: 'content', severity: 'high', recommendation: 'Expand content significantly (currently under 100 words)' },

  // Technical SEO Issues
  sitemap_missing: { points: -8, category: 'technical', severity: 'medium', recommendation: 'Create and submit an XML sitemap' },
  robots_missing: { points: -5, category: 'technical', severity: 'low', recommendation: 'Add a robots.txt file' },
  no_ssl: { points: -15, category: 'technical', severity: 'high', recommendation: 'Install SSL certificate and migrate to HTTPS' },
  mixed_content: { points: -10, category: 'technical', severity: 'medium', recommendation: 'Fix mixed content warnings (HTTP resources on HTTPS pages)' },
  canonical_missing: { points: -10, category: 'technical', severity: 'high', recommendation: 'Add canonical tags to prevent duplicate content issues' },
  canonical_error: { points: -8, category: 'technical', severity: 'medium', recommendation: 'Fix canonical tag self-reference errors' },
  mobile_viewport_missing: { points: -10, category: 'technical', severity: 'high', recommendation: 'Add mobile viewport meta tag' },
  broken_internal_link: { points: -5, category: 'technical', severity: 'medium', recommendation: 'Fix broken internal links', maxTotal: -20 },
  server_error: { points: -10, category: 'technical', severity: 'high', recommendation: 'Fix 4xx/5xx server errors' },

  // Core Web Vitals
  lcp_slow: { points: -8, category: 'performance', severity: 'medium', recommendation: 'Improve Largest Contentful Paint (currently >2.5s)' },
  lcp_very_slow: { points: -12, category: 'performance', severity: 'high', recommendation: 'Urgently improve Largest Contentful Paint (currently >4s)' },
  cls_bad: { points: -6, category: 'performance', severity: 'medium', recommendation: 'Reduce Cumulative Layout Shift (currently >0.1)' },
  cls_very_bad: { points: -10, category: 'performance', severity: 'high', recommendation: 'Urgently reduce Cumulative Layout Shift (currently >0.25)' },
  inp_slow: { points: -6, category: 'performance', severity: 'medium', recommendation: 'Improve Interaction to Next Paint (currently >200ms)' },
  inp_very_slow: { points: -10, category: 'performance', severity: 'high', recommendation: 'Urgently improve Interaction to Next Paint (currently >500ms)' },

  // Structural Issues
  orphan_page: { points: -10, category: 'structure', severity: 'medium', recommendation: 'Add internal links to this page' },
  images_missing_alt: { points: -6, category: 'structure', severity: 'low', recommendation: 'Add alt tags to images (>50% missing)' },
  no_schema: { points: -3, category: 'structure', severity: 'low', recommendation: 'Implement schema markup for rich results' },
  broken_breadcrumbs: { points: -4, category: 'structure', severity: 'low', recommendation: 'Fix breadcrumb navigation' }
};

// =============================================================================
// BONUS DEFINITIONS
// =============================================================================

const BONUSES = {
  cwv_pass: { points: 5, description: 'All Core Web Vitals pass' },
  fast_page_speed: { points: 3, description: 'Page speed under 1.5s' },
  schema_implemented: { points: 3, description: 'Schema markup implemented correctly' },
  no_broken_links: { points: 2, description: 'Zero broken internal links' },
  proper_heading_hierarchy: { points: 3, description: 'Proper heading hierarchy on all pages' },
  all_images_have_alt: { points: 2, description: 'All images have alt tags' }
};

// =============================================================================
// QUICK WIN PRIORITIES
// =============================================================================

const QUICK_WIN_PRIORITY = {
  'cannibalization': 100,
  'missing_h1': 80,
  'title_missing': 75,
  'title_too_short': 70,
  'canonical_missing': 70,
  'lcp_very_slow': 65,
  'lcp_slow': 60,
  'heading_hierarchy_skipped': 50,
  'meta_description_missing': 40,
  'default': 30
};

// =============================================================================
// MAIN SCORING FUNCTION
// =============================================================================

/**
 * Calculate the full score for a scanned site
 * @param {Object} scanData - The raw scan data
 * @returns {Object} Complete scoring result
 */
function calculateScore(scanData) {
  const {
    url,
    pagesAnalyzed,
    issues = [],
    conflicts = [],
    bonusesEarned = [],
    cwv = {},
    scanTime = null
  } = scanData;

  // Step 1: Start with 100
  let score = 100;
  const appliedDeductions = [];
  const appliedBonuses = [];

  // Step 2: Count and weight cannibalization conflicts
  const weightedConflicts = calculateWeightedConflicts(conflicts);
  const conflictCount = conflicts.length;

  // Step 3: Get URLs involved in conflicts (for same-intent multiplier)
  const conflictingUrls = new Set();
  conflicts.forEach(c => {
    conflictingUrls.add(c.pageA);
    conflictingUrls.add(c.pageB);
  });

  // Step 4: Apply all deductions
  const deductionTracker = {}; // Track totals for capped deductions

  issues.forEach(issue => {
    const deductionDef = DEDUCTIONS[issue.type];
    if (!deductionDef) return;

    let points = deductionDef.points;

    // Apply same-intent multiplier if issue is on a conflicting page
    if (issue.url && conflictingUrls.has(issue.url)) {
      points = Math.round(points * CONFIG.sameIntentMultiplier);
    }

    // Handle max total cap (e.g., broken links max -20)
    if (deductionDef.maxTotal) {
      const key = issue.type;
      deductionTracker[key] = (deductionTracker[key] || 0) + points;
      if (deductionTracker[key] < deductionDef.maxTotal) {
        points = 0; // Already hit max
      } else if (deductionTracker[key] - points >= deductionDef.maxTotal) {
        // This deduction would exceed max, cap it
        points = deductionDef.maxTotal - (deductionTracker[key] - points);
      }
    }

    score += points; // points are negative

    appliedDeductions.push({
      type: issue.type,
      category: deductionDef.category,
      severity: deductionDef.severity,
      points: points,
      url: issue.url || null,
      recommendation: deductionDef.recommendation
    });
  });

  const scoreAfterDeductions = score;

  // Step 5: Apply bonus points
  let totalBonuses = 0;
  bonusesEarned.forEach(bonusType => {
    const bonusDef = BONUSES[bonusType];
    if (!bonusDef) return;

    if (totalBonuses + bonusDef.points <= CONFIG.maxBonusPoints) {
      totalBonuses += bonusDef.points;
      appliedBonuses.push({
        type: bonusType,
        points: bonusDef.points,
        description: bonusDef.description
      });
    }
  });

  score += totalBonuses;
  const scoreAfterBonuses = score;

  // Step 6: Calculate and apply cannibalization cap
  const baseCap = getCannibalizationCap(weightedConflicts);
  
  // Step 7: Apply page count adjustment
  const pagesInConflicts = conflictingUrls.size;
  const conflictPercentage = pagesAnalyzed > 0 ? (pagesInConflicts / pagesAnalyzed) * 100 : 100;
  const capAdjustment = getPageCountAdjustment(conflictPercentage);
  const adjustedCap = Math.min(100, baseCap + capAdjustment);

  const capApplied = score > adjustedCap;
  if (capApplied) {
    score = adjustedCap;
  }

  // Step 8: Floor at 0, ceiling at 100
  score = Math.max(0, Math.min(100, Math.round(score)));

  // Step 9: Determine grade
  const gradeInfo = getGrade(score);

  // Generate Quick Wins
  const quickWins = generateQuickWins(conflicts, appliedDeductions);

  // Calculate category scores (for display only)
  const categoryScores = calculateCategoryScores(appliedDeductions, appliedBonuses);

  return {
    scanId: generateId(),
    url: url,
    scannedAt: new Date().toISOString(),
    pagesAnalyzed: pagesAnalyzed,
    scanTimeSeconds: scanTime,

    score: {
      final: score,
      grade: gradeInfo.grade,
      label: gradeInfo.label,
      color: gradeInfo.color,
      message: CONFIG.gradeMessages[gradeInfo.grade]
    },

    calculationBreakdown: {
      startingScore: 100,
      totalDeductions: scoreAfterDeductions - 100,
      totalBonuses: totalBonuses,
      scoreBeforeCap: scoreAfterBonuses,
      cannibalizationCap: baseCap,
      pageCountAdjustment: capAdjustment,
      adjustedCap: adjustedCap,
      capApplied: capApplied
    },

    cannibalization: {
      conflictCount: conflictCount,
      weightedConflictCount: weightedConflicts,
      conflicts: conflicts.map(c => ({
        type: c.type,
        severity: CONFIG.conflictSeverity[c.type] || 1.0,
        pageA: c.pageA,
        pageB: c.pageB,
        signalMatches: c.signals || []
      }))
    },

    categories: categoryScores,

    issues: appliedDeductions,

    bonuses: appliedBonuses,

    quickWins: quickWins
  };
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Calculate weighted conflict count based on severity
 */
function calculateWeightedConflicts(conflicts) {
  return conflicts.reduce((sum, conflict) => {
    const weight = CONFIG.conflictSeverity[conflict.type] || 1.0;
    return sum + weight;
  }, 0);
}

/**
 * Get the cap based on weighted conflicts
 */
function getCannibalizationCap(weightedConflicts) {
  for (const [maxConflicts, cap] of CONFIG.cannibalizationCaps) {
    if (weightedConflicts <= maxConflicts) {
      return cap;
    }
  }
  return 44; // Default to lowest
}

/**
 * Get page count adjustment for the cap
 */
function getPageCountAdjustment(conflictPercentage) {
  for (const [maxPercentage, adjustment] of CONFIG.pageCountAdjustments) {
    if (conflictPercentage < maxPercentage) {
      return adjustment;
    }
  }
  return 0;
}

/**
 * Get grade info based on score
 */
function getGrade(score) {
  for (const [minScore, grade, label, color] of CONFIG.gradeThresholds) {
    if (score >= minScore) {
      return { grade, label, color };
    }
  }
  return { grade: 'F', label: 'Failing', color: '#dc2626' };
}

/**
 * Generate prioritized quick wins
 */
function generateQuickWins(conflicts, deductions, maxWins = 5) {
  const wins = [];

  // Add cannibalization as top priority if present
  if (conflicts.length > 0) {
    wins.push({
      priority: 1,
      issue: 'Keyword Cannibalization',
      description: `${conflicts.length} page${conflicts.length > 1 ? 's are' : ' is'} competing for similar keywords`,
      recommendation: 'Consolidate pages or differentiate their keyword targeting',
      impact: 'High'
    });
  }

  // Add other issues sorted by priority
  const sortedDeductions = [...deductions].sort((a, b) => {
    const priorityA = QUICK_WIN_PRIORITY[a.type] || QUICK_WIN_PRIORITY.default;
    const priorityB = QUICK_WIN_PRIORITY[b.type] || QUICK_WIN_PRIORITY.default;
    return priorityB - priorityA;
  });

  // Dedupe by type and add to wins
  const seenTypes = new Set();
  for (const ded of sortedDeductions) {
    if (seenTypes.has(ded.type)) continue;
    if (wins.length >= maxWins) break;

    seenTypes.add(ded.type);
    wins.push({
      priority: wins.length + 1,
      issue: formatIssueName(ded.type),
      description: ded.url ? `Issue found on ${ded.url}` : 'Issue detected',
      recommendation: ded.recommendation,
      impact: ded.severity === 'high' || ded.severity === 'critical' ? 'High' : 'Medium'
    });
  }

  return wins;
}

/**
 * Calculate category scores for display
 */
function calculateCategoryScores(deductions, bonuses) {
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
      categories[ded.category].score += ded.points; // points are negative
    }
  });

  // Floor at 0
  Object.keys(categories).forEach(key => {
    categories[key].score = Math.max(0, categories[key].score);
  });

  return categories;
}

/**
 * Format issue type to readable name
 */
function formatIssueName(type) {
  return type
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Generate a simple unique ID
 */
function generateId() {
  return 'scan_' + Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
}

// =============================================================================
// CONFLICT DETECTION FUNCTIONS
// =============================================================================

/**
 * Detect cannibalization conflicts between pages
 * @param {Array} pages - Array of page data objects
 * @returns {Array} Array of detected conflicts
 */
function detectConflicts(pages) {
  const conflicts = [];

  for (let i = 0; i < pages.length; i++) {
    for (let j = i + 1; j < pages.length; j++) {
      const pageA = pages[i];
      const pageB = pages[j];
      const conflict = detectConflictBetweenPages(pageA, pageB);
      
      if (conflict) {
        conflicts.push(conflict);
      }
    }
  }

  return conflicts;
}

/**
 * Check if two pages have a cannibalization conflict
 */
function detectConflictBetweenPages(pageA, pageB) {
  const signals = [];

  // Check title similarity
  const titleSimilarity = calculateSimilarity(
    pageA.title?.toLowerCase() || '',
    pageB.title?.toLowerCase() || ''
  );
  if (titleSimilarity > 0.7) {
    signals.push('title_similarity');
  }

  // Check H1 similarity
  const h1Similarity = calculateSimilarity(
    pageA.h1?.toLowerCase() || '',
    pageB.h1?.toLowerCase() || ''
  );
  if (h1Similarity > 0.7) {
    signals.push('h1_similarity');
  }

  // Check URL slug similarity
  const slugA = extractSlug(pageA.url);
  const slugB = extractSlug(pageB.url);
  const slugSimilarity = calculateSimilarity(slugA, slugB);
  if (slugSimilarity > 0.6) {
    signals.push('url_similarity');
  }

  // Check meta description similarity
  const metaSimilarity = calculateSimilarity(
    pageA.metaDescription?.toLowerCase() || '',
    pageB.metaDescription?.toLowerCase() || ''
  );
  if (metaSimilarity > 0.6) {
    signals.push('meta_similarity');
  }

  // Determine conflict type based on signals
  if (signals.length >= 2) {
    let type = 'intent_collision';

    // Exact title match = exact match conflict
    if (titleSimilarity > 0.95) {
      type = 'exact_match';
    } else if (titleSimilarity > 0.7 || h1Similarity > 0.7) {
      type = 'high_overlap';
    } else if (signals.includes('url_similarity')) {
      type = 'url_cannibalization';
    }

    // Check for title duplicate specifically
    if (pageA.title && pageB.title && pageA.title === pageB.title) {
      type = signals.length === 1 ? 'title_duplicate' : 'exact_match';
    }

    return {
      type: type,
      pageA: pageA.url,
      pageB: pageB.url,
      signals: signals,
      titleSimilarity: titleSimilarity,
      h1Similarity: h1Similarity
    };
  }

  return null;
}

/**
 * Calculate Jaccard similarity between two strings
 * Simple implementation - replace with more sophisticated algo if needed
 */
function calculateSimilarity(str1, str2) {
  if (!str1 || !str2) return 0;
  if (str1 === str2) return 1;

  const words1 = new Set(str1.split(/\s+/).filter(w => w.length > 2));
  const words2 = new Set(str2.split(/\s+/).filter(w => w.length > 2));

  if (words1.size === 0 || words2.size === 0) return 0;

  const intersection = new Set([...words1].filter(x => words2.has(x)));
  const union = new Set([...words1, ...words2]);

  return intersection.size / union.size;
}

/**
 * Extract slug from URL for comparison
 */
function extractSlug(url) {
  try {
    const pathname = new URL(url).pathname;
    return pathname
      .replace(/^\/|\/$/g, '')
      .replace(/[-_]/g, ' ')
      .toLowerCase();
  } catch {
    return url.toLowerCase();
  }
}

// =============================================================================
// ISSUE DETECTION FUNCTIONS
// =============================================================================

/**
 * Detect all issues on a page
 * @param {Object} pageData - Page data from crawler
 * @returns {Array} Array of detected issues
 */
function detectIssues(pageData) {
  const issues = [];
  const url = pageData.url;

  // Title tag checks
  if (!pageData.title) {
    issues.push({ type: 'title_missing', url });
  } else if (pageData.title.length < 30) {
    issues.push({ type: 'title_too_short', url });
  } else if (pageData.title.length > 60) {
    issues.push({ type: 'title_too_long', url });
  }

  // H1 checks
  if (!pageData.h1 || pageData.h1Count === 0) {
    issues.push({ type: 'missing_h1', url });
  } else if (pageData.h1Count > 1) {
    issues.push({ type: 'multiple_h1', url });
  }

  // Heading hierarchy check
  if (pageData.headingHierarchyBroken) {
    issues.push({ type: 'heading_hierarchy_skipped', url });
  }

  // Meta description checks
  if (!pageData.metaDescription) {
    issues.push({ type: 'meta_description_missing', url });
  } else if (pageData.metaDescription.length < 70) {
    issues.push({ type: 'meta_description_too_short', url });
  } else if (pageData.metaDescription.length > 160) {
    issues.push({ type: 'meta_description_too_long', url });
  }

  // Content checks
  if (pageData.wordCount !== undefined) {
    if (pageData.wordCount < 100) {
      issues.push({ type: 'very_thin_content', url });
    } else if (pageData.wordCount < 300) {
      issues.push({ type: 'thin_content', url });
    }
  }

  // Technical checks
  if (!pageData.hasCanonical) {
    issues.push({ type: 'canonical_missing', url });
  }

  if (!pageData.hasMobileViewport) {
    issues.push({ type: 'mobile_viewport_missing', url });
  }

  // Broken links
  if (pageData.brokenLinks && pageData.brokenLinks.length > 0) {
    pageData.brokenLinks.forEach(() => {
      issues.push({ type: 'broken_internal_link', url });
    });
  }

  // Core Web Vitals
  if (pageData.lcp) {
    if (pageData.lcp > 4000) {
      issues.push({ type: 'lcp_very_slow', url });
    } else if (pageData.lcp > 2500) {
      issues.push({ type: 'lcp_slow', url });
    }
  }

  if (pageData.cls !== undefined) {
    if (pageData.cls > 0.25) {
      issues.push({ type: 'cls_very_bad', url });
    } else if (pageData.cls > 0.1) {
      issues.push({ type: 'cls_bad', url });
    }
  }

  if (pageData.inp) {
    if (pageData.inp > 500) {
      issues.push({ type: 'inp_very_slow', url });
    } else if (pageData.inp > 200) {
      issues.push({ type: 'inp_slow', url });
    }
  }

  return issues;
}

/**
 * Detect site-wide issues
 * @param {Object} siteData - Site-level data from crawler
 * @returns {Array} Array of detected issues
 */
function detectSiteIssues(siteData) {
  const issues = [];

  if (!siteData.hasSitemap) {
    issues.push({ type: 'sitemap_missing', url: siteData.url });
  }

  if (!siteData.hasRobotsTxt) {
    issues.push({ type: 'robots_missing', url: siteData.url });
  }

  if (!siteData.hasSSL) {
    issues.push({ type: 'no_ssl', url: siteData.url });
  }

  if (siteData.hasMixedContent) {
    issues.push({ type: 'mixed_content', url: siteData.url });
  }

  return issues;
}

/**
 * Detect bonuses earned
 * @param {Object} siteData - Site-level data
 * @param {Array} pageIssues - All page issues
 * @returns {Array} Array of bonus types earned
 */
function detectBonuses(siteData, pageIssues) {
  const bonuses = [];

  // Check CWV pass
  const cwvIssues = pageIssues.filter(i => 
    ['lcp_slow', 'lcp_very_slow', 'cls_bad', 'cls_very_bad', 'inp_slow', 'inp_very_slow'].includes(i.type)
  );
  if (cwvIssues.length === 0 && siteData.cwvMeasured) {
    bonuses.push('cwv_pass');
  }

  // Check page speed
  if (siteData.avgPageSpeed && siteData.avgPageSpeed < 1500) {
    bonuses.push('fast_page_speed');
  }

  // Check schema
  if (siteData.hasSchema) {
    bonuses.push('schema_implemented');
  }

  // Check broken links
  const brokenLinkIssues = pageIssues.filter(i => i.type === 'broken_internal_link');
  if (brokenLinkIssues.length === 0) {
    bonuses.push('no_broken_links');
  }

  // Check heading hierarchy
  const hierarchyIssues = pageIssues.filter(i => i.type === 'heading_hierarchy_skipped');
  if (hierarchyIssues.length === 0) {
    bonuses.push('proper_heading_hierarchy');
  }

  // Check alt tags
  if (siteData.allImagesHaveAlt) {
    bonuses.push('all_images_have_alt');
  }

  return bonuses;
}

// =============================================================================
// MAIN ENTRY POINT FOR FULL SCAN
// =============================================================================

/**
 * Process a complete site scan
 * @param {Object} crawlResult - Raw crawl data
 * @returns {Object} Complete scoring result
 */
function processScan(crawlResult) {
  const { url, pages, siteData, scanTime } = crawlResult;

  // Detect all issues
  let allIssues = [];
  pages.forEach(page => {
    const pageIssues = detectIssues(page);
    allIssues = allIssues.concat(pageIssues);
  });

  // Add site-wide issues
  const siteIssues = detectSiteIssues(siteData);
  allIssues = allIssues.concat(siteIssues);

  // Detect conflicts
  const conflicts = detectConflicts(pages);

  // Detect bonuses
  const bonusesEarned = detectBonuses(siteData, allIssues);

  // Calculate score
  const result = calculateScore({
    url: url,
    pagesAnalyzed: pages.length,
    issues: allIssues,
    conflicts: conflicts,
    bonusesEarned: bonusesEarned,
    scanTime: scanTime
  });

  return result;
}

// =============================================================================
// EXPORTS
// =============================================================================

module.exports = {
  calculateScore,
  detectConflicts,
  detectIssues,
  detectSiteIssues,
  detectBonuses,
  processScan,
  CONFIG,
  DEDUCTIONS,
  BONUSES
};
