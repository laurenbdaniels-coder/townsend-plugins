# Validation Plan (Pre-Launch Testing + UAT) — Template

The "does the built thing actually work?" artifact, produced near the end of delivery, before launch-gtm takes over. Route by risk first (`standards/decision-frameworks.md` validation routing): beta/pilot for usage-and-fit risk or one-way doors; experiment for implementation risk behind two-way doors; staged dial-up with guardrails when you'd roll forward anyway. Experiment *design* (hypotheses, sample size, guardrails) lives with metrics-iteration — this template covers functional validation and user acceptance. *Solo founder: sections 1, 2, and the pass/fail table, nothing more.*

---

## TL;DR & So What

*Max 2 paragraphs: (1) what's being validated, how, and against what pre-committed bar, (2) what a fail means — fix, hold, or descope — and who decides.*

## 1. Scope and pass bar (pre-committed)

*What's being validated, and what result = ready. Write the pass/fail thresholds NOW, before testing starts — post-hoc thresholds always pass. Include the disconfirming case: what result would mean "do not ship."*

- In scope / out of scope: TK
- Pass bar: TK · Fail means: fix / hold / descope — decided by: TK

## 2. Functional test coverage

*Trace to the PRD: happy path, edge cases, error/empty/loading states, the "wrong user" path (permissions), and the tracking plan (events fire correctly — a story isn't done if its events don't). Reference the PRD's acceptance criteria rather than restating them; list only the additions.*

## 3. UAT — user acceptance

*Persona-based test cases that mirror real workflows, not feature checklists: "As [persona], accomplish [job] starting from [realistic entry point]." Recruit testers matching the target segment (positioning doc). Capture pass/fail plus friction notes verbatim.*

| # | Persona | Scenario (organic workflow) | Steps | Expected | Pass/Fail | Notes |
|---|---|---|---|---|---|---|
| 1 | TK | TK | TK | TK | TK | TK |

*If UAT keeps surfacing requirement misunderstandings, that's a requirements problem, not a testing problem — flag it back to requirements-prd rather than patching test cases.*

## 4. Results and verdict

*Results against the Section 1 bar, verbatim. Verdict: ready / ready-with-known-issues (list them, with the support handoff) / not ready (path to ready, owner, date). Findings worth remembering file to `85-insight-log.md`.*

## Quality bar

- [ ] Pass/fail bar written before testing began
- [ ] Validation route chosen by risk (doors), stated in one sentence
- [ ] Unhappy paths and permissions cases tested, not just the demo path
- [ ] Tracking-plan events verified firing
- [ ] UAT scenarios mirror organic workflows with real target-segment testers
- [ ] Verdict is committal; known issues have a support handoff
- [ ] AI features: eval plan (references/ai-eval.md) passed before this verdict
