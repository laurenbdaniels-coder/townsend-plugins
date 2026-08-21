# Go/No-Go — Template

Use for launches that warrant a gate. **Door check first** (`standards/decision-frameworks.md`): two-way-door launches take the lightweight path — readiness checklist + dial-up plan with guardrail metrics; reserve the full treatment below for one-way doors (pricing, migrations, deprecations, public commitments) and contested launches. Scale to the launch tier — a Tier 3 change needs none of this. A no-go or hold is a respectable outcome: make "not ready, here's the path to green" as easy to say as "go."

---

## TL;DR & So What

*Max 2 paragraphs: (1) launching what, when, and the overall GREEN/YELLOW/RED read with the one-sentence reason, (2) the recommendation (go / no-go / hold) and the single biggest open risk.*

## 1. Decision criteria (previously aligned)

*List the go/no-go criteria the team aligned on earlier — in the PRD, beta-exit doc, or validation plan. **If no pre-aligned criteria exist, that's the real gap: draft them and get agreement before assessing readiness against them.** Criteria written the night before the meeting will be criteria the launch already meets.*

## 2. Contested topics

*Any open, contested calls: options with benefits, risks and mitigations, plus a written recommendation. Drive to alignment or disagree-and-commit; record the outcome in the decision log.*

## 3. Readiness by workstream

*Named sign-offs — "green" from nobody is red. Cut rows that don't apply to this tier.*

| Workstream | Status | Signed off by | Notes |
|---|---|---|---|
| Tech readiness | TK | TK | TK |
| Validation / UAT | TK | TK | *exit criteria met per validation plan* |
| Analytics / instrumentation | TK | TK | *tracking-plan events verified; success metrics measurable day 1* |
| Support / ops | TK | TK | *monitoring live, known-issues list + escalation path handed over* |
| Comms / enablement | TK | TK | TK |
| Legal / compliance | TK | TK | TK |
| Rollback / dial-down | TK | TK | *what triggers rollback after "go," who executes, how fast* |
| AI quality *(if generative features ship)* | TK | TK | *evals passed, drift monitoring live — per delivery-planning's ai-eval.md* |

## 4. Risk register

*Carried forward from `60-delivery-risk-register.md` (open risks that survive into market exposure) plus launch-specific ones.*

| # | Risk (impact / blast radius) | Criticality | Mitigated at launch? | Path to green |
|---|---|---|---|---|
| 1 | TK | TK | Yes/No — TK | TK |

## 5. Decision and the learning hook

*Record the decision (go / no-go / hold, by whom, date). Then — at this gate, not later — book the landing review: calendar entry 2–6 weeks out, owner named, scored against the pre-registered success criteria. Reviews scheduled "when things settle down" never happen.*

## Quality bar

- [ ] Door check ran; treatment matches door type and launch tier
- [ ] Criteria were aligned before this doc, or their absence is named as the first fix
- [ ] Every workstream row has a named sign-off
- [ ] Rollback row filled: trigger, owner, speed
- [ ] Open `[ASSUMPTION]`s on load-bearing claims surfaced, not buried
- [ ] Landing review booked with an owner before the meeting ends
