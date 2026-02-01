/**
 * Siloq Scoring Algorithm - Test Cases v1.1.1
 * Run with: node siloq-scoring-tests.js
 */

const {
  calculateScore,
  detectConflicts,
  detectDuplicates,
  processScan,
  CONFIG,
  DEDUCTIONS,
  BONUSES
} = require('./siloq-scoring-algorithm');

// =============================================================================
// TEST HELPERS
// =============================================================================

let passed = 0;
let failed = 0;

function assert(condition, testName) {
  if (condition) {
    console.log(`  ✅ PASS: ${testName}`);
    passed++;
    return true;
  } else {
    console.log(`  ❌ FAIL: ${testName}`);
    failed++;
    return false;
  }
}

// =============================================================================
// TEST CASES
// =============================================================================

console.log('🧪 Running Siloq Scoring Algorithm Tests v1.1.1\n');
console.log('='.repeat(70));

// -----------------------------------------------------------------------------
// Test 1: crystallizedcouture.com (the problem case)
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 1: crystallizedcouture.com (Problem Case)');
console.log('-'.repeat(70));

const test1 = calculateScore({
  url: 'https://crystallizedcouture.com/',
  pagesAnalyzed: 1,
  issues: [
    { type: 'missing_h1', url: 'https://crystallizedcouture.com/' },
    { type: 'heading_hierarchy_skipped', url: 'https://crystallizedcouture.com/' },
    { type: 'title_too_short', url: 'https://crystallizedcouture.com/' },
    { type: 'sitemap_missing', url: 'https://crystallizedcouture.com/' }
  ],
  conflicts: [
    { type: 'intent_collision', pageA: '/page1/', pageB: '/page2/', signals: ['title_similarity', 'h1_similarity'] },
    { type: 'intent_collision', pageA: '/page1/', pageB: '/page3/', signals: ['title_similarity'] },
    { type: 'intent_collision', pageA: '/page2/', pageB: '/page3/', signals: ['h1_similarity'] }
  ],
  bonusesEarned: []
});

console.log(`  Score: ${test1.score.final} (${test1.score.grade})`);
console.log(`  Expected: <60 (D- or F), NOT 93/B+`);
console.log(`  Deductions: ${test1.calculationBreakdown.totalDeductions}`);
console.log(`  Cap (3 conflicts): ${test1.calculationBreakdown.cannibalizationCap}`);
assert(test1.score.final < 60, 'Problem case scores below 60');

// -----------------------------------------------------------------------------
// Test 2: Clean site with minor issues
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 2: Clean Site with Minor Issues');
console.log('-'.repeat(70));

const test2 = calculateScore({
  url: 'https://cleansite.com/',
  pagesAnalyzed: 10,
  issues: [
    { type: 'meta_description_too_long', url: 'https://cleansite.com/' },
    { type: 'no_schema', url: 'https://cleansite.com/' }
  ],
  conflicts: [],
  bonusesEarned: ['cwv_pass', 'fast_page_speed', 'no_broken_links', 'proper_heading_hierarchy']
});

console.log(`  Score: ${test2.score.final} (${test2.score.grade})`);
console.log(`  Deductions: ${test2.calculationBreakdown.totalDeductions}`);
console.log(`  Bonuses: +${test2.calculationBreakdown.totalBonuses}`);
assert(test2.score.final >= 95, 'Clean site scores 95+');
assert(test2.score.grade === 'A+' || test2.score.grade === 'A', 'Clean site gets A grade');

// -----------------------------------------------------------------------------
// Test 3: Large site with few conflicts (page count adjustment)
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 3: Large Site with Few Conflicts (Page Count Adjustment)');
console.log('-'.repeat(70));

const test3 = calculateScore({
  url: 'https://bigsite.com/',
  pagesAnalyzed: 500,
  issues: [
    { type: 'lcp_very_slow', url: 'https://bigsite.com/' },
    { type: 'cls_very_bad', url: 'https://bigsite.com/' },
    { type: 'canonical_missing', url: 'https://bigsite.com/page1/' },
    { type: 'canonical_missing', url: 'https://bigsite.com/page2/' },
    { type: 'canonical_missing', url: 'https://bigsite.com/page3/' },
    { type: 'multiple_h1', url: 'https://bigsite.com/' }
  ],
  conflicts: [
    { type: 'high_overlap', pageA: '/services/', pageB: '/what-we-do/', signals: ['title_similarity', 'h1_similarity'] },
    { type: 'high_overlap', pageA: '/about/', pageB: '/about-us/', signals: ['title_similarity'] }
  ],
  bonusesEarned: []
});

console.log(`  Score: ${test3.score.final} (${test3.score.grade})`);
console.log(`  Conflicts: 2 (${(4/500*100).toFixed(2)}% of pages)`);
console.log(`  Page count adjustment: +${test3.calculationBreakdown.pageCountAdjustment}`);
console.log(`  Base cap: ${test3.calculationBreakdown.cannibalizationCap}, Adjusted: ${test3.calculationBreakdown.adjustedCap}`);
assert(test3.calculationBreakdown.pageCountAdjustment === 15, 'Page count adjustment is +15 for <5%');

// -----------------------------------------------------------------------------
// Test 4: Site with 1 minor conflict
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 4: Site with 1 Minor Conflict (title_duplicate = 0.75x)');
console.log('-'.repeat(70));

const test4 = calculateScore({
  url: 'https://smallsite.com/',
  pagesAnalyzed: 20,
  issues: [
    { type: 'title_too_long', url: 'https://smallsite.com/page1/' },
    { type: 'title_too_long', url: 'https://smallsite.com/page2/' }
  ],
  conflicts: [
    { type: 'title_duplicate', pageA: '/blog/post1/', pageB: '/blog/post2/', signals: ['title_similarity'] }
  ],
  bonusesEarned: ['cwv_pass', 'proper_heading_hierarchy', 'no_broken_links']
});

console.log(`  Score: ${test4.score.final} (${test4.score.grade})`);
console.log(`  Weighted conflicts: ${test4.cannibalization.weightedConflictCount}`);
console.log(`  Cap: ${test4.calculationBreakdown.cannibalizationCap}`);
assert(test4.cannibalization.weightedConflictCount === 0.75, 'title_duplicate weighted at 0.75');
assert(test4.score.final >= 80 && test4.score.final < 95, 'Minor conflict penalized but not destroyed');

// -----------------------------------------------------------------------------
// Test 5: Regression - More conflicts = worse (or same) score
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 5: Regression - More Conflicts = Worse Score');
console.log('-'.repeat(70));

const test5a = calculateScore({
  url: 'https://site-a.com/',
  pagesAnalyzed: 10,
  issues: [
    { type: 'missing_h1', url: '/' },
    { type: 'title_too_short', url: '/' },
    { type: 'sitemap_missing', url: '/' }
  ],
  conflicts: [
    { type: 'intent_collision', pageA: '/a/', pageB: '/b/', signals: ['title_similarity'] },
    { type: 'intent_collision', pageA: '/a/', pageB: '/c/', signals: ['title_similarity'] },
    { type: 'intent_collision', pageA: '/b/', pageB: '/c/', signals: ['title_similarity'] }
  ],
  bonusesEarned: []
});

const test5b = calculateScore({
  url: 'https://site-b.com/',
  pagesAnalyzed: 10,
  issues: [
    { type: 'title_too_short', url: '/' }
  ],
  conflicts: [
    { type: 'intent_collision', pageA: '/a/', pageB: '/b/', signals: ['title_similarity'] },
    { type: 'intent_collision', pageA: '/a/', pageB: '/c/', signals: ['title_similarity'] },
    { type: 'intent_collision', pageA: '/b/', pageB: '/c/', signals: ['title_similarity'] },
    { type: 'intent_collision', pageA: '/d/', pageB: '/e/', signals: ['title_similarity'] },
    { type: 'intent_collision', pageA: '/d/', pageB: '/f/', signals: ['title_similarity'] }
  ],
  bonusesEarned: []
});

console.log(`  Site A (3 conflicts, more issues): ${test5a.score.final} (${test5a.score.grade})`);
console.log(`  Site B (5 conflicts, fewer issues): ${test5b.score.final} (${test5b.score.grade})`);
assert(test5b.score.final <= test5a.score.final, 'More conflicts = same or worse score');

// -----------------------------------------------------------------------------
// Test 6: Same Intent Multiplier
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 6: Same Intent Multiplier (1.3x on conflicting pages)');
console.log('-'.repeat(70));

const test6 = calculateScore({
  url: 'https://multiplier-test.com/',
  pagesAnalyzed: 10,
  issues: [
    // This H1 is on a page involved in a conflict - should get 1.3x
    { type: 'missing_h1', url: '/cheer-jackets/' },
    // This H1 is NOT on a conflicting page - no multiplier
    { type: 'missing_h1', url: '/about/' }
  ],
  conflicts: [
    { type: 'intent_collision', pageA: '/cheer-jackets/', pageB: '/jackets/cheer/', signals: ['title_similarity'] }
  ],
  bonusesEarned: []
});

// missing_h1 = -15 normally
// /cheer-jackets/ should be -15 × 1.3 = -19.5 ≈ -20 (rounded)
// /about/ should be -15
// Total should be around -35, not -30

const expectedWithMultiplier = -35; // -20 + -15
const actualDeductions = test6.calculationBreakdown.totalDeductions;

console.log(`  Expected deductions (with multiplier): ~${expectedWithMultiplier}`);
console.log(`  Actual deductions: ${actualDeductions}`);
console.log(`  (Without multiplier would be -30)`);
assert(actualDeductions < -30, 'Same intent multiplier increases deductions');

// -----------------------------------------------------------------------------
// Test 7: Bonus Cap at +15
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 7: Bonus Cap at +15');
console.log('-'.repeat(70));

const test7 = calculateScore({
  url: 'https://bonus-test.com/',
  pagesAnalyzed: 10,
  issues: [],
  conflicts: [],
  bonusesEarned: [
    'cwv_pass',           // +5
    'schema_implemented', // +3
    'fast_page_speed',    // +3
    'no_broken_links',    // +2
    'proper_heading_hierarchy', // +3
    'all_images_have_alt' // +2 (total would be +18)
  ]
});

console.log(`  Bonuses earned: ${test7.bonuses.length}`);
console.log(`  Total bonus points: +${test7.calculationBreakdown.totalBonuses}`);
console.log(`  (Max possible: +${5+3+3+2+3+2} = +18)`);
assert(test7.calculationBreakdown.totalBonuses <= 15, 'Bonus cap enforced at 15');

// -----------------------------------------------------------------------------
// Test 8: Conflict Type Weighting
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 8: Conflict Type Weighting (exact_match > title_duplicate)');
console.log('-'.repeat(70));

const test8a = calculateScore({
  url: 'https://exact-match.com/',
  pagesAnalyzed: 10,
  issues: [],
  conflicts: [
    { type: 'exact_match', pageA: '/a/', pageB: '/b/', signals: ['title_similarity', 'h1_similarity', 'url_similarity'] }
  ],
  bonusesEarned: []
});

const test8b = calculateScore({
  url: 'https://title-duplicate.com/',
  pagesAnalyzed: 10,
  issues: [],
  conflicts: [
    { type: 'title_duplicate', pageA: '/a/', pageB: '/b/', signals: ['title_similarity'] }
  ],
  bonusesEarned: []
});

console.log(`  Exact match (1.5x): cap = ${test8a.calculationBreakdown.cannibalizationCap}, weighted = ${test8a.cannibalization.weightedConflictCount}`);
console.log(`  Title duplicate (0.75x): cap = ${test8b.calculationBreakdown.cannibalizationCap}, weighted = ${test8b.cannibalization.weightedConflictCount}`);
assert(test8a.cannibalization.weightedConflictCount === 1.5, 'exact_match weighted at 1.5');
assert(test8b.cannibalization.weightedConflictCount === 0.75, 'title_duplicate weighted at 0.75');
assert(test8a.calculationBreakdown.cannibalizationCap < test8b.calculationBreakdown.cannibalizationCap, 'exact_match has lower cap');

// -----------------------------------------------------------------------------
// Test 9: Score Floor at 0
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 9: Score Floor at 0 (Never Negative)');
console.log('-'.repeat(70));

const test9 = calculateScore({
  url: 'https://disaster.com/',
  pagesAnalyzed: 5,
  issues: [
    { type: 'title_missing', url: '/page1/' },
    { type: 'title_missing', url: '/page2/' },
    { type: 'missing_h1', url: '/page1/' },
    { type: 'missing_h1', url: '/page2/' },
    { type: 'missing_h1', url: '/page3/' },
    { type: 'no_ssl', url: '/' },
    { type: 'sitemap_missing', url: '/' },
    { type: 'robots_missing', url: '/' },
    { type: 'lcp_very_slow', url: '/' },
    { type: 'cls_very_bad', url: '/' },
    { type: 'canonical_missing', url: '/page1/' },
    { type: 'canonical_missing', url: '/page2/' },
    { type: 'canonical_missing', url: '/page3/' }
  ],
  conflicts: [
    { type: 'exact_match', pageA: '/a/', pageB: '/b/', signals: ['title_similarity'] },
    { type: 'exact_match', pageA: '/c/', pageB: '/d/', signals: ['title_similarity'] },
    { type: 'exact_match', pageA: '/e/', pageB: '/f/', signals: ['title_similarity'] },
    { type: 'exact_match', pageA: '/g/', pageB: '/h/', signals: ['title_similarity'] },
    { type: 'exact_match', pageA: '/i/', pageB: '/j/', signals: ['title_similarity'] },
    { type: 'exact_match', pageA: '/k/', pageB: '/l/', signals: ['title_similarity'] },
    { type: 'exact_match', pageA: '/m/', pageB: '/n/', signals: ['title_similarity'] }
  ],
  bonusesEarned: []
});

console.log(`  Deductions: ${test9.calculationBreakdown.totalDeductions}`);
console.log(`  Final score: ${test9.score.final}`);
console.log(`  Grade: ${test9.score.grade} (${test9.score.label})`);
assert(test9.score.final >= 0, 'Score never goes negative');
assert(test9.score.grade === 'F', 'Disaster site gets F');

// -----------------------------------------------------------------------------
// Test 10: API Response Schema Validation
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 10: API Response Schema Validation');
console.log('-'.repeat(70));

const test10 = calculateScore({
  url: 'https://schema-test.com/',
  pagesAnalyzed: 5,
  issues: [{ type: 'title_too_short', url: '/' }],
  conflicts: [{ type: 'intent_collision', pageA: '/a/', pageB: '/b/', signals: ['title_similarity'] }],
  bonusesEarned: ['cwv_pass']
});

const requiredFields = ['scanId', 'url', 'scannedAt', 'pagesAnalyzed', 'score', 'calculationBreakdown', 'cannibalization', 'categories', 'issues', 'bonuses', 'quickWins'];
const scoreFields = ['final', 'grade', 'label', 'color', 'message'];
const breakdownFields = ['startingScore', 'totalDeductions', 'totalBonuses', 'scoreBeforeCap', 'cannibalizationCap', 'pageCountAdjustment', 'adjustedCap', 'capApplied'];

const missingRoot = requiredFields.filter(f => !(f in test10));
const missingScore = scoreFields.filter(f => !(f in test10.score));
const missingBreakdown = breakdownFields.filter(f => !(f in test10.calculationBreakdown));

console.log(`  Root fields: ${missingRoot.length === 0 ? 'All present ✓' : 'Missing: ' + missingRoot.join(', ')}`);
console.log(`  Score fields: ${missingScore.length === 0 ? 'All present ✓' : 'Missing: ' + missingScore.join(', ')}`);
console.log(`  Breakdown fields: ${missingBreakdown.length === 0 ? 'All present ✓' : 'Missing: ' + missingBreakdown.join(', ')}`);

assert(missingRoot.length === 0, 'All root fields present');
assert(missingScore.length === 0, 'All score fields present');
assert(missingBreakdown.length === 0, 'All breakdown fields present');

// -----------------------------------------------------------------------------
// Test 11: detectDuplicates Function
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 11: detectDuplicates Function');
console.log('-'.repeat(70));

const pages = [
  { url: '/page1/', title: 'Buy Shoes Online', metaDescription: 'Shop our collection of shoes.' },
  { url: '/page2/', title: 'Buy Shoes Online', metaDescription: 'Different description here.' },
  { url: '/page3/', title: 'Unique Title', metaDescription: 'Shop our collection of shoes.' },
  { url: '/page4/', title: 'Another Unique', metaDescription: 'Totally unique meta.' }
];

const duplicates = detectDuplicates(pages);
const titleDups = duplicates.filter(d => d.type === 'duplicate_title');
const metaDups = duplicates.filter(d => d.type === 'duplicate_meta');

console.log(`  Title duplicates found: ${titleDups.length}`);
console.log(`  Meta duplicates found: ${metaDups.length}`);
assert(titleDups.length === 1, 'Detects 1 duplicate title');
assert(metaDups.length === 1, 'Detects 1 duplicate meta');

// -----------------------------------------------------------------------------
// Test 12: SEO Category Reflects Cannibalization
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 12: SEO Category Reflects Cannibalization');
console.log('-'.repeat(70));

const test12a = calculateScore({
  url: 'https://no-conflicts.com/',
  pagesAnalyzed: 10,
  issues: [],
  conflicts: [],
  bonusesEarned: []
});

const test12b = calculateScore({
  url: 'https://has-conflicts.com/',
  pagesAnalyzed: 10,
  issues: [],
  conflicts: [
    { type: 'intent_collision', pageA: '/a/', pageB: '/b/', signals: ['title_similarity'] },
    { type: 'intent_collision', pageA: '/c/', pageB: '/d/', signals: ['title_similarity'] }
  ],
  bonusesEarned: []
});

console.log(`  No conflicts - SEO category: ${test12a.categories.seo.score}`);
console.log(`  2 conflicts - SEO category: ${test12b.categories.seo.score}`);
assert(test12a.categories.seo.score === 100, 'No conflicts = 100 SEO score');
assert(test12b.categories.seo.score < 100, 'Conflicts reduce SEO score');

// -----------------------------------------------------------------------------
// Test 13: Cap Table Entry for 5 Conflicts
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 13: Cap Table Entry for 5 Conflicts');
console.log('-'.repeat(70));

const test13 = calculateScore({
  url: 'https://five-conflicts.com/',
  pagesAnalyzed: 10,
  issues: [],
  conflicts: [
    { type: 'intent_collision', pageA: '/a/', pageB: '/b/', signals: ['title_similarity'] },
    { type: 'intent_collision', pageA: '/c/', pageB: '/d/', signals: ['title_similarity'] },
    { type: 'intent_collision', pageA: '/e/', pageB: '/f/', signals: ['title_similarity'] },
    { type: 'intent_collision', pageA: '/g/', pageB: '/h/', signals: ['title_similarity'] },
    { type: 'intent_collision', pageA: '/i/', pageB: '/j/', signals: ['title_similarity'] }
  ],
  bonusesEarned: []
});

console.log(`  5 conflicts - Cap: ${test13.calculationBreakdown.cannibalizationCap}`);
console.log(`  Expected: 64`);
assert(test13.calculationBreakdown.cannibalizationCap === 64, 'Cap for 5 conflicts is 64');

// =============================================================================
// SUMMARY
// =============================================================================

console.log('\n' + '='.repeat(70));
console.log('📋 QUICK WINS OUTPUT EXAMPLE');
console.log('='.repeat(70));
console.log('\nFrom Test 1 (crystallizedcouture.com):');
test1.quickWins.forEach(win => {
  console.log(`  ${win.priority}. ${win.issue} (${win.impact} impact, ${win.estimatedPoints || '?'} points)`);
  console.log(`     → ${win.recommendation}`);
});

console.log('\n' + '='.repeat(70));
console.log(`📊 TEST RESULTS: ${passed}/${passed + failed} tests passed`);
console.log('='.repeat(70));

if (failed > 0) {
  console.log('\n⚠️  Some tests failed. Review output above.');
  process.exit(1);
} else {
  console.log('\n✅ All tests passed!');
  process.exit(0);
}
