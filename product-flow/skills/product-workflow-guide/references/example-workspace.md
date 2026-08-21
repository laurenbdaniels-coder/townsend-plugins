# Example workspace (miniature, filled)

A compressed example of what a healthy `product-workspace/` looks like for a fictional product, "Shelfie" — an app that helps independent bookshops manage online reservations. Use it to calibrate tone, TL;DR quality, and stage-log hygiene. Real artifacts are longer; the TL;DRs are the part to imitate closely.

## `00-product-context.md`

```markdown
## TL;DR & So What
Shelfie helps independent bookshops take online reservations without a full
e-commerce stack. Maya (solo founder, ex-bookseller) has interviewed 8 shop
owners and validated the problem; strategy and a first roadmap exist, and the
reservations MVP ("resv") is in requirements.

So what: next step is finishing the resv PRD and getting it critiqued before
committing 6 weeks to the build. Biggest open risk: shops' willingness to pay
is still an assumption.

## Product
Shelfie — online reservations for independent bookshops.

## User profile
Solo founder (Maya). Lightest artifacts, minimum ceremony.

## Constraints
Nights-and-weekends build until June; budget ~$0; no team.

## Stage log
| stage | artifact file | initiative | date | status |
|---|---|---|---|---|
| 1 | 10-discovery-problem-statement.md | product | 2026-05-02 | validated |
| 2 | 20-positioning-doc.md | product | 2026-05-10 | done |
| 3 | 30-strategy-onepager.md | product | 2026-05-16 | done |
| 4 | 40-roadmap-now-next-later.md | product | 2026-05-20 | done |
| 5 | 50-requirements-resv-onepager.md | resv | 2026-05-28 | in review |

## Changelog
- 2026-05-28: resv one-pager added; WTP flagged as top assumption.
```

## `10-discovery-problem-statement.md` (excerpt)

```markdown
## TL;DR & So What
Independent bookshop owners lose walk-in sales when customers call to ask
"do you have X?" and nobody can answer fast — 6 of 8 owners interviewed
described losing a specific sale this way in the last month, and 5 already
pay for a workaround (extra phone staff hours or a clunky webshop they hate).
One disconfirming signal: the 2 largest shops interviewed have staff for this
and felt no pain.

So what: the problem is real for small shops (1–4 staff) — that's the segment.
Next move: check what these shops use today (stage 2) before designing anything.

## Evidence for
- "Last Tuesday a regular called about the new Ishiguro; by the time we
  checked the shelf she'd ordered it on Amazon." — Owner, 2-person shop (I3)
- 5/8 pay real money today: avg ~9 staff-hours/week on phone availability checks.
...

## Evidence against
- Both 5+ staff shops: "not a top-ten problem." Segment boundary, not a kill signal.

## Verdict
VALIDATED for shops with 1–4 staff (n=8, one metro area — widen before scaling bets).
```

## `80-metrics-landing-review.md` (excerpt, written after the resv launch)

```markdown
## TL;DR & So What
The reservations MVP partially landed: 34% of pilot shops' regulars used it in
month one (target: 30%), but repeat use fell to 11% by week 4 (target: 25%)
because confirmation emails land in spam. We promised "reservations become the
default way regulars check availability" — that has not happened yet.

So what: fix deliverability before any new feature work; re-review in 3 weeks.
If repeat use doesn't clear 20% by then, revisit the opportunity — the roadmap's
"Next" items stay frozen until this lands.

## Targets vs. actuals (pre-registered in 50-requirements-resv-onepager.md)
| Metric | Target | Actual | Verdict |
|---|---|---|---|
| Regulars using resv, month 1 | 30% | 34% | hit |
| Repeat use, week 4 | 25% | 11% | miss |

## Decision
FIX (deliverability), not build. Learning logged; roadmap re-scored 2026-07-02.
```

Notice what makes these work: TL;DRs never exceed two paragraphs, name real numbers, admit disconfirming evidence, and end with the next move; the stage log tracks initiatives (`product` vs `resv`) so a second feature loop never overwrites the first.
