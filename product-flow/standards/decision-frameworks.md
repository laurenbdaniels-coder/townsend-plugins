# Decision Frameworks (suite-wide)

Shared decision logic. Skills route gate, validation, and scope decisions through these tests instead of re-deriving them.

## One-way vs. two-way doors

Before any gate or big commitment, ask: **is this decision cheaply reversible?**

- **Two-way door** (reversible): decide fast, ship with monitoring, roll back if wrong. Lightweight or no gate.
- **One-way door** (irreversible or expensive to reverse): full gate treatment — written decision criteria, evidence review, explicit sign-off.

One-way-door signals: public commitments, pricing changes, data migrations, deprecations, contractual promises, brand positioning, anything customers build workflows on.

## Validation routing (before GA)

- **Beta or pilot** when: you need live usage data on whether it will be used as expected, product-market-fit risk is real, edge cases could create operational burden, or the launch is a one-way door. Exit criteria are written **before** the beta starts — a beta without pre-committed exit criteria is a soft launch wearing a beta badge.
- **GA with experimentation** when the risk is in implementation choices fully within the team's control and doors are two-way.
- **Both** when the feature could harm business outcomes — if you'd roll back on issues, instrument for it.
- **Straight GA with staged dial-up + guardrail metrics** when doors are two-way and you'd roll forward through issues.
- **AI/generative features always add an eval gate** (golden set, scoring rubric, drift monitoring) — deterministic pass/fail testing doesn't cover non-deterministic outputs.

## Pre-committed thresholds

For evidence-driven decisions (invest/pass, wedge selection, beta exit, experiment verdicts): write the go/no-go criteria AND the disconfirming criteria *before* gathering evidence, so the evidence can't be curated to fit the preferred answer. Test the riskiest assumption first — the one that kills the idea if false, not the one easiest to confirm. Post-hoc thresholds always pass; that's why they don't count (label them post-hoc when they're all you have).

## Bets, not features

Frame roadmap commitments as bets: customer problem, expected outcome, named assumptions, and a **decision/review date**. A bet without a review date is a feature promise. **Zombie-bet rule:** a bet that survives two review cycles without new supporting evidence gets a discovery task or a kill decision — not a third quiet renewal.

## When something comes in fast, go slower

Late-breaking "urgent" asks get a written mini decision doc (options, risks with mitigations, recommendation), not a hallway yes — speed pressure is when thrash is created. *Solo-founder caveat:* this applies to one-way doors; a solo founder's advantage is deciding fast on two-way doors, and this rule should never take that away.

## Decision hygiene

For any contested choice: write each option with benefits, risks *and mitigations*; make a recommendation; represent every stated point of view before escalating. Record one-way doors and operational-load impacts explicitly. Drive to alignment or disagree-and-commit — and log the outcome where the stage's artifact records decisions.
