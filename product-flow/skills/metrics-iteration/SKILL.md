---
name: metrics-iteration
description: Guides post-launch measurement and iteration — instrumenting and reviewing metrics with a layered framework stack (North Star review, AARRR funnel, HEART, OKRs), designing honest A/B experiments with guardrails, running landing reviews that compare results to the original hypothesis, and turning findings into next-step decisions. Use when the user asks whether a launch worked, how to measure a shipped product or feature, mentions KPIs, analytics, OKRs, A/B tests, experiments, retention, funnels, or "what should we do next" after shipping. (Defining a new North Star metric belongs to strategy-vision.)
---

# Metrics & Iteration (Stage 8)

Help the user find out whether it worked and decide what happens next: double down, fix, or kill. This stage closes the loop — its output re-enters discovery and the roadmap.

## Workspace protocol

Read `product-workspace/00-product-context.md`, `30-strategy-northstar.md` (or the strategy one-pager), `50-requirements-*.md` (the pre-registered success metrics), `70-launch-brief.md` (targets + landing review date), and `70-launch-learnings.md` (the qualitative signal — objections, friction, feedback themes). The whole point is comparing results to what was *promised* — surface those promises verbatim. Save outputs as `product-workspace/80-metrics-<artifact>.md` (`80-metrics-framework.md`, `80-metrics-experiment-<name>.md`, `80-metrics-landing-review.md`) and update the Stage log.


### Suite conventions (apply even when files are missing)

- Missing context or upstream artifacts never block: proceed anyway, ask at most 2 orienting questions in one round, tag unverified inherited claims `[ASSUMPTION]`, and offer to create a minimal `00-product-context.md` (product one-liner, user profile, authoring mode, stage log) when saving.
- Evidence discipline per this plugin's `standards/evidence-rules.md`: every claim gets a source line, an `[ASSUMPTION]` tag (stating what would confirm or kill it), or a `TK` placeholder — never an invented number, quote, or name. Stakeholder-bound docs surface open assumptions in their own section (tag-and-warn, never block).
- Before any gate or big commitment, run the door check from `standards/decision-frameworks.md`: two-way doors (reversible) get lightweight treatment; one-way doors (pricing, migrations, deprecations, public commitments) get the full gate.
- Stage log in `00-product-context.md` (create if absent): a table `| stage | artifact file | initiative | date | status |` — add or update your row whenever you save an artifact. Durable learnings file as INSIGHT-NNN entries in `85-insight-log.md`, the single cross-initiative memory (claim, source, confidence, implications, status; log within 48h; disconfirmed entries get marked and linked, never deleted).
- Repeat runs for a new feature/initiative: include an initiative slug in filenames — `NN-<stage>-<slug>-<artifact>.md` — and never overwrite another initiative's files. Product-level singletons (context, positioning, strategy, insight log) update in place with a dated changelog line at the bottom.
- Adapt depth to the user profile in the context file (ask once if unknown): solo founder → lightest artifact, minimum ceremony; team PM → emphasize alignment and decision rationale; learner → briefly explain why each step exists as you go. If authoring mode is `guide-only`, structure, question, and critique so the user writes the artifact themselves; if they still ask you to draft, nudge once toward their own words, then help fully — it's their product.
- One round of questions max before drafting; then proceed on documented `[ASSUMPTION]`s rather than interrogating.

## Framework menu — layer, don't pick one

| Framework | What it measures | Pick it when |
|---|---|---|
| **North Star + input tree** (popularized by Amplitude) | One value-delivery metric, decomposed into 3–5 team-movable inputs. | Strategic alignment across teams; already defined in stage 3 — here you instrument and review it. |
| **AARRR (pirate metrics)** (Dave McClure) | Acquisition → Activation → Retention → Revenue → Referral funnel. | Growth diagnosis: finding WHERE the business leaks. Startups and funnel-shaped products. |
| **HEART** (Google) | Happiness, Engagement, Adoption, Retention, Task success — each as Goals → Signals → Metrics. | Feature/UX-level quality measurement; complements the business-level views. |
| **OKRs** | Quarterly objectives + 3–5 measurable key results. | Org-wide goal alignment; pairs with North Star (NSM endures, OKRs are the quarter's push). KRs are outcomes, never feature checklists. |
| **A/B experimentation** | Causal answers: hypothesis → primary metric → guardrails → adequate sample → verdict. | Enough traffic for significance; decisions worth the rigor. Low traffic → say so honestly and use painted-door tests, cohort comparisons, or qualitative signal instead. |

Typical stack: North Star (strategy) + AARRR or HEART (diagnosis) + experiments (causal decisions) + OKRs (org rhythm).

## Workflow

1. **Instrument the promises.** Build the metrics framework doc: North Star + inputs, the funnel or HEART table for the product/feature, and where each number comes from — pull the tracking plan from `50-requirements-*` so metrics map to real events, and flag any metric with no event behind it. Distinguish leading vs. lagging, and value metrics vs. **vanity metrics** (raw signups, page views, cumulative anything — flag them on sight).
2. **Check data quality before trusting any number.** Event volumes vs. expectations, platforms/versions missing, bot or internal traffic, events broken by recent releases. A broken event looks exactly like a failed feature — rule that out before writing a verdict.
3. **Run the landing review** when there's a shipped thing to judge (`80-metrics-landing-review.md`):
   - Restate the original hypothesis and targets *verbatim* from the PRD/launch brief. If no pre-registered targets exist (lightweight path or skipped stages), set targets now with the user and label them **post-hoc** — honest late targets beat no targets.
   - Actuals vs. targets, with honest confounders (seasonality, marketing pushes, selection effects) — and fold in the qualitative signal from `70-launch-learnings.md`.
   - Revisit the initiative's risky assumptions (assumption map / PRD risks): mark each resolved, disproven, or still open — an initiative can hit its targets while its riskiest assumption stays untested.
   - Record rough actual effort/elapsed time vs. the roadmap's scored estimate, with a one-line "worth it?" call; append the ratio to the learning log so future scoring gets calibrated.
   - Verdict: **landed / partially landed / missed** — and the decision: double down / fix specific friction / stop. "We shipped it" is not a verdict.
   - If the decision is **stop**: plan the sunset like a small launch — user notice with dates, a migration path for anyone depending on it, and a flag/code removal ticket. Killed features that linger half-alive cost more than they did to build.
   - What surprised us — the gap between what we predicted and what happened is where the learning lives.
   - What we learned that changes the roadmap or reopens discovery — write the specific item, not "iterate" — and the named decision-maker who saw this review and made the call.
   - Goal-status updates along the way use `references/goal-status.md`: "We are [green/yellow/red] because…", strict color definitions, the outcome rule (delivery line AND metric-moved line), and a path to green that names actions, owners, and dates.
4. **Design experiments properly** when causal questions arise (`80-metrics-experiment-<name>.md`):
   - Hypothesis: "We believe [change] will cause [effect] for [segment] because [mechanism]."
   - ONE primary metric, pre-registered. Guardrail metrics that must not degrade (retention, performance, revenue, support load).
   - Sample size / duration set *before* starting (help compute it); no peeking — or use sequential methods deliberately; run full business cycles (whole weeks).
   - Readout: effect size with confidence interval, guardrail status, decision, and "what we'd test next." Stat-sig but trivial → say "not worth shipping complexity" out loud.
5. **Diagnose with the funnel** when growth is the question: compute stage-to-stage conversion, find the biggest leak *for the best-fit segment*, and generate 2–3 hypotheses about the leak from qualitative signal (support tickets, session replays, discovery quotes) before proposing fixes.
6. **Maintain the insight log** (`85-insight-log.md` — the suite's single cross-initiative memory). Every landing review, experiment readout, and lost-deal debrief files at least one INSIGHT-NNN entry: claim (one sentence, falsifiable) | source | confidence | implications | what changed because of it | status. New evidence contradicting an entry marks it disconfirmed and links the newer entry — never delete; the trail of changed minds is the point. If the "what changed" column is chronically empty, the team is doing measurement theater — flag it.
7. **Close the loop.** Route findings explicitly: metric misses and surprises → discovery-validation (new interview questions) and roadmap-prioritization (re-scoring with real data); wins → strategy-vision check-in (does the North Star still hold?); competitive surprises or objection themes → a market-positioning refresh; recurring themes → the next quarter's OKRs.

## Artifact rules

Every artifact starts with `## TL;DR & So What` — **max 2 paragraphs, plain language**: (1) what the numbers say happened, (2) the verdict and the single next move. A stakeholder should get the truth from the TL;DR alone.

## Pitfalls checklist

- [ ] Data quality checked before any conclusion — a broken event was ruled out first.
- [ ] Vanity metrics flagged; North Star is leading + value-based (not revenue/MAU).
- [ ] Landing review compares against *pre-registered* targets, quoted verbatim.
- [ ] Every review/readout ends in a decision (double down / fix / stop), not "interesting."
- [ ] Experiments: one primary metric, guardrails, pre-set sample size, no silent peeking.
- [ ] Stat-sig ≠ meaningful; effect size judged against complexity cost.
- [ ] Low-traffic honesty: no fake A/B rigor where samples can't support it.
- [ ] OKR key results are outcomes with numbers, not feature lists.
- [ ] Learning log's "what changed" column is non-empty over time.
