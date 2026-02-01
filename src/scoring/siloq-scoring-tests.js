/**
 * Siloq Scoring Algorithm - Test Cases
 * Run with: node siloq-scoring-tests.js
 */

const {
  calculateScore,
  detectConflicts,
  processScan,
  CONFIG
} = require('./siloq-scoring-algorithm');

// =============================================================================
// TEST CASES
// =============================================================================

console.log('🧪 Running Siloq Scoring Algorithm Tests\n');
console.log('='.repeat(60));

// -----------------------------------------------------------------------------
// Test 1: crystallizedcouture.com (the problem case)
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 1: crystallizedcouture.com (Problem Case)');
console.log('-'.repeat(60));

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

console.log(`Score: ${test1.score.final} (${test1.score.grade})`);
console.log(`Expected: ~57 or lower (D- or F), NOT 93/B+`);
console.log(`✅ ${test1.score.final < 60 ? 'PASS' : 'FAIL'} - Score creates urgency`);
console.log('\nBreakdown:');
console.log(`  Starting: 100`);
console.log(`  Deductions: ${test1.calculationBreakdown.totalDeductions}`);
console.log(`  Cap (3 conflicts): ${test1.calculationBreakdown.cannibalizationCap}`);
console.log(`  Cap applied: ${test1.calculationBreakdown.capApplied}`);

// -----------------------------------------------------------------------------
// Test 2: Clean site with minor issues
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 2: Clean Site with Minor Issues');
console.log('-'.repeat(60));

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

console.log(`Score: ${test2.score.final} (${test2.score.grade})`);
console.log(`Expected: 95-100 (A or A+)`);
console.log(`✅ ${test2.score.final >= 95 ? 'PASS' : 'FAIL'} - Clean site gets good score`);
console.log('\nBreakdown:');
console.log(`  Deductions: ${test2.calculationBreakdown.totalDeductions}`);
console.log(`  Bonuses: +${test2.calculationBreakdown.totalBonuses}`);

// -----------------------------------------------------------------------------
// Test 3: Large site with few conflicts (page count adjustment)
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 3: Large Site with Few Conflicts');
console.log('-'.repeat(60));

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

console.log(`Score: ${test3.score.final} (${test3.score.grade})`);
console.log(`Conflicts: 2 (but only ${(4/500*100).toFixed(1)}% of pages)`);
console.log(`Page count adjustment: +${test3.calculationBreakdown.pageCountAdjustment} to cap`);
console.log(`Adjusted cap: ${test3.calculationBreakdown.adjustedCap}`);
console.log(`\nNote: Score is low due to technical issues, not cannibalization`);

// -----------------------------------------------------------------------------
// Test 4: Site with 1 minor conflict
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 4: Site with 1 Minor Conflict');
console.log('-'.repeat(60));

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

console.log(`Score: ${test4.score.final} (${test4.score.grade})`);
console.log(`Expected: ~80-89 (B range) - penalized but not destroyed`);
console.log(`✅ ${test4.score.final >= 80 && test4.score.final < 90 ? 'PASS' : 'NEEDS REVIEW'}`);
console.log('\nBreakdown:');
console.log(`  Weighted conflicts: ${test4.cannibalization.weightedConflictCount} (title_duplicate = 0.75x)`);
console.log(`  Base cap: ${test4.calculationBreakdown.cannibalizationCap}`);

// -----------------------------------------------------------------------------
// Test 5: Verify more conflicts = worse score (regression test)
// -----------------------------------------------------------------------------
console.log('\n📊 TEST 5: More Conflicts = Worse Score (Regression)');
console.log('-'.repeat(60));

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

console.log(`Site A (3 conflicts, more issues): ${test5a.score.final} (${test5a.score.grade})`);
console.log(`Site B (5 conflicts, fewer issues): ${test5b.score.final} (${test5b.score.grade})`);
console.log(`✅ ${test5b.score.final <= test5a.score.final ? 'PASS' : 'FAIL'} - More conflicts = same or worse score`);

// -----------------------------------------------------------------------------
// Summary
// -----------------------------------------------------------------------------
console.log('\n' + '='.repeat(60));
console.log('📋 QUICK WINS OUTPUT EXAMPLE');
console.log('='.repeat(60));
console.log('\nFrom Test 1 (crystallizedcouture.com):');
test1.quickWins.forEach(win => {
  console.log(`  ${win.priority}. ${win.issue} (${win.impact} impact)`);
  console.log(`     → ${win.recommendation}`);
});

console.log('\n' + '='.repeat(60));
console.log('✅ All tests complete. Review results above.');
console.log('='.repeat(60));
