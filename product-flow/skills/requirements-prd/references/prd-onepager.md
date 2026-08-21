# One-Pager / PRD — Template

One template, two weights. The one-pager decides "are we aligned enough to start?"; the full PRD decides "what exactly are we building?" Start at one-pager weight and add the full-PRD sections only when the decision demands them. Evidence rules bind every claim; inherit upstream content (discovery evidence, positioning segment, strategy metrics, roadmap success signal) rather than reinventing it.

---

## TL;DR & So What

*Max 2 paragraphs: (1) what we're building and for whom, (2) why now and what happens next.*

## One-pager core (always)

- **Problem** — *with evidence: counts and verbatim quotes from discovery ("6 of 8 owners…"), source lines per `standards/evidence-rules.md`. Unverified claims get `[ASSUMPTION]` tags.*
- **Goals** — *the behaviors we enable or change; each maps to a success metric below.*
- **Non-goals** — *as load-bearing as goals; real exclusions someone argued for, with reasons (reasons prevent relitigating).*
- **Target user & job** — *inherited from positioning's best-fit segment; job statement, not a demographic.*
- **Success metrics** — *every criterion gets a target, a named owner, and a review date at approval — the landing review collects on these.*

| Success criterion | Target | Owner | Review date |
|---|---|---|---|
| TK | TK | TK | TK |

- **Proposed solution** — *what and why, not how — implementation belongs to engineers. A TK referencing a known pain beats confident filler.*
- **Open questions** — *each with an owner and a date.*
- **Risks & mitigations** — *seeded from the discovery assumption map's still-open high-importance rows, evidence rating kept.*
- **Dependencies** · **Material constraints & NFRs** — *just the 2–3 that matter; a one-pager that ignores performance, privacy, or abuse isn't lean, it's blind.*
- **Assumptions register** — *every `[ASSUMPTION]` in the doc:*

| `[ASSUMPTION]` | Confirmed by | Killed by | Check by (date/gate) |
|---|---|---|---|
| TK | TK | TK | TK |

- **Pivot criteria** — *what evidence would change this direction entirely? A doc that can't answer that is a commitment, not a plan — run the door check.*

## Full PRD adds (when the decision demands detail)

- **User flows** and **edge cases**: error / empty / loading states; permissions & authorization edges (*who must NOT be able to do this?*); abuse/misuse potential; migration & backward compatibility for existing users and data.
- **NFR sweep** — one line each, "n/a" allowed but must be written: performance · reliability (what breaks and how badly?) · scale · security · privacy/data handling · accessibility · compliance · localization · observability (how will we know it's broken?) · AI quality/safety evals (if generative — see delivery-planning's ai-eval.md).
- **Tracking plan** — `| event | fires when | properties | feeds which metric |` for every success metric plus surrounding funnel steps; one naming convention; minimum collection, no PII in properties without privacy review.
- **Rollout & flagging plan** (with delivery-planning) and **out-of-scope**: later vs. never.
- **Traceability rule:** every must-have requirement maps to a validated pain from discovery, or carries an `[ASSUMPTION]` tag that must clear before build.

## Stories & acceptance criteria (handoff into delivery)

*"As a [user], I want [capability], so that [benefit]" — sliced by user value (INVEST), not architecture layer. Job-story alternative when the persona adds nothing: "When [situation], I want [motivation], so I can [outcome]." Each story: Given/When/Then AC covering the happy path, key edge cases, the failure path, and the "wrong user" path — written before development. Fold tracking-plan events into AC: a story isn't done if its events don't fire.*

## Quality bar

- [ ] Non-goals contain real exclusions with reasons
- [ ] Every problem claim sourced or `[ASSUMPTION]`-tagged; register complete with confirm/kill/check-by
- [ ] Success metrics have target + owner + review date — not "improve engagement"
- [ ] Solution says what/why, not how
- [ ] Pivot criteria stated; door check run if this is a commitment
- [ ] Full PRD: NFR sweep complete (or consciously n/a'd), tracking plan present, unhappy paths covered
- [ ] Read by engineering + design before any estimate is treated as real
