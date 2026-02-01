# Dev Handoff: Lead Gen Scoring Algorithm Fix

## The Problem

Our current scoring is broken. A site with 3 cannibalization conflicts, no H1, broken heading hierarchy, and no sitemap is getting a **93/B+**. That's insane. 

Nobody is going to pay us to fix their site when we tell them they're at 93%. The score needs to create appropriate urgency while still being honest.

---

## What Needs to Change

### 1. The Math is Backwards (Critical Fix)

**Current behavior:** We're averaging category scores, so perfect 100s in Structure/Performance/SEO mask the failures in Content.

**New behavior:** 
- Start at 100
- Apply deductions for every issue found
- Apply bonus points for excellence (max +15)
- THEN apply a hard cap based on cannibalization conflicts
- The cap can only lower the score, never raise it

**Why this order matters:** If we cap first then deduct, a site with MORE cannibalization can score higher than a site with less. That's backwards.

### 2. Cannibalization Must Tank the Score

If a site has cannibalization—which is literally the problem we solve—they cannot get an A. Period.

**New caps:**
| Conflicts | Max Possible Score |
|-----------|-------------------|
| 0 | 100 (A+) |
| 1 | 84 (B) |
| 2 | 79 (C+) |
| 3 | 74 (C) |
| 4 | 69 (D+) |
| 5-6 | 64 (D) |
| 7-9 | 54 (D-) |
| 10+ | 44 (F) |

### 3. Add Page Count Context

3 conflicts on a 10-page site = catastrophic (30% of pages affected)
3 conflicts on a 500-page site = minor (0.6% affected)

Adjust the cap based on what % of pages are involved:
- >20% involved = no adjustment
- 10-20% = +5 to cap
- 5-10% = +10 to cap
- <5% = +15 to cap

### 4. Quick Wins Section

After the score, show 3 prioritized fixes. This is what converts leads.

```
🔧 Quick Wins:
1. Fix cannibalization: /page-a/ and /page-b/ compete for same keyword (High impact)
2. Add H1 tag to homepage (Medium impact)
3. Expand title tag on /services/ (Low impact)
```

---

## Full Spec Document

I've attached `siloq-scoring-algorithm-v1.1.md` with everything:

- Exact deduction values for every issue type
- Conflict detection logic (what counts as a conflict)
- Same Intent Multiplier (1.3x for issues on conflicting pages)
- Bonus points for excellence
- Grade thresholds and messaging
- 4 worked examples
- Full API response schema
- Implementation checklist (MVP vs V1.1 vs V2)

---

## Priority Order

**Ship immediately (MVP):**
1. Fix the math order (deductions first, then cap)
2. Implement hard caps for conflicts
3. Update grade thresholds
4. Fix the display

**Fast follow (V1.1):**
- Page count adjustment
- Bonus points
- Quick Wins output
- Conflict type classification

---

## Expected Results

Using the new algorithm, crystallizedcouture.com goes from:
- **Old:** 93/B+ 
- **New:** 57/D-

That's a score that makes someone say "I need help."

---

## Questions?

Let me know if anything in the spec is unclear. The examples section walks through the math step by step.

@Ahmad Raja - Please review the API response schema and let me know if it works for the frontend.

@Jumar Juaton - The conflict detection signals are in Section 1. Start with title + H1 + URL similarity for MVP.

Let's get this fixed before we push more traffic to the tool.

— Kyle
