---
name: roadmap-prioritization
description: Guides backlog prioritization and roadmap creation — scoring items with RICE, ICE, WSJF, Kano, or MoSCoW and building an outcome-oriented Now/Next/Later roadmap with stakeholder-ready rationale. Use when the user asks what to build first, how to prioritize features or a backlog, mentions RICE or prioritization frameworks, needs a product roadmap, must cut scope for a release, or has to justify priority calls to stakeholders.
---

# Prioritization & Roadmap (Stage 4)

Help the user turn "everything we could do" into a defensible ordering and a roadmap that communicates intent without making promises they'll regret.

## Workspace protocol

Read `product-workspace/00-product-context.md` and `30-strategy-onepager.md` first — **strategy is the filter; frameworks only rank what strategy admits.** Also check `10-discovery-*` (evidence for impact claims) and `80-metrics-*` (data for reach claims). Save outputs as `product-workspace/40-roadmap-<artifact>.md` (`40-roadmap-scored-backlog.md`, `40-roadmap-now-next-later.md`) and update the Stage log.


### Suite conventions (apply even when files are missing)

- Missing context or upstream artifacts never block: proceed anyway, ask at most 2 orienting questions in one round, tag unverified inherited claims `[ASSUMPTION]`, and offer to create a minimal `00-product-context.md` (product one-liner, user profile, authoring mode, stage log) when saving.
- Evidence discipline per this plugin's `standards/evidence-rules.md`: every claim gets a source line, an `[ASSUMPTION]` tag (stating what would confirm or kill it), or a `TK` placeholder — never an invented number, quote, or name. Stakeholder-bound docs surface open assumptions in their own section (tag-and-warn, never block).
- Before any gate or big commitment, run the door check from `standards/decision-frameworks.md`: two-way doors (reversible) get lightweight treatment; one-way doors (pricing, migrations, deprecations, public commitments) get the full gate.
- Stage log in `00-product-context.md` (create if absent): a table `| stage | artifact file | initiative | date | status |` — add or update your row whenever you save an artifact. Durable learnings file as INSIGHT-NNN entries in `85-insight-log.md`, the single cross-initiative memory (claim, source, confidence, implications, status; log within 48h; disconfirmed entries get marked and linked, never deleted).
- Repeat runs for a new feature/initiative: include an initiative slug in filenames — `NN-<stage>-<slug>-<artifact>.md` — and never overwrite another initiative's files. Product-level singletons (context, positioning, strategy, insight log) update in place with a dated changelog line at the bottom.
- Adapt depth to the user profile in the context file (ask once if unknown): solo founder → lightest artifact, minimum ceremony; team PM → emphasize alignment and decision rationale; learner → briefly explain why each step exists as you go. If authoring mode is `guide-only`, structure, question, and critique so the user writes the artifact themselves; if they still ask you to draft, nudge once toward their own words, then help fully — it's their product.
- One round of questions max before drafting; then proceed on documented `[ASSUMPTION]`s rather than interrogating.

## Framework menu — layered by decision level, not competing

| Framework | Formula / method | Pick it when |
|---|---|---|
| **RICE** (Intercom) | (Reach × Impact × Confidence) ÷ Effort. Reach = users/quarter; Impact on the discrete scale 0.25 / 0.5 / 1 / 2 / 3; Confidence as %; Effort in person-weeks or -months. | 15+ item backlog, product with real usage data, need numerical rigor for stakeholders. |
| **ICE** (Sean Ellis) | Impact × Confidence × Ease, each 1–10. | Speed over precision: growth experiments, early stage, triaging 30 ideas in 20 minutes. |
| **WSJF** (SAFe) | Cost of Delay (user-business value + time criticality + risk reduction & opportunity enablement) ÷ job size. | Time-sensitive items, portfolio-level sequencing, SAFe orgs; naturally rewards small batches. |
| **Kano** | Classify features as must-be / performance / delighter via paired functional-dysfunctional user questions. | Designing a feature *mix* (table stakes vs. differentiation), not ordering a backlog. |
| **MoSCoW** | Must / Should / Could / Won't for a specific release. | Scope negotiation with non-technical stakeholders around a fixed date. |

Layer them: WSJF for big bets across the portfolio, RICE/ICE inside the team backlog, MoSCoW for release scope, Kano for what goes in one initiative. Warn if the user treats any single framework as gospel — scores structure the conversation; they don't make the decision.

## Workflow

1. **Apply the strategy filter first.** For each candidate item: which strategic bet or North Star input does it serve? Items serving none go to a "strategy orphans" list — either the strategy is incomplete or the item is a distraction; make the user decide which, don't score orphans.
2. **Choose the framework(s)** from the menu based on backlog size, data availability, and audience. State your recommendation in two sentences.
3. **Score honestly, together.** Build the scoring table, but make the user supply or bless every input. Enforce honesty: Reach counts users in the target segment (per positioning/strategy), not all users — widening the segment to inflate a score is a positioning decision, not a scoring input; Reach claims should cite data or be flagged as guesses; check `80-metrics-*` landing reviews for past estimate-vs-actual ratios to calibrate Effort and Confidence; Confidence caps at 50% for items with no discovery evidence (link to `10-discovery-*` where it exists); Effort comes from whoever builds, not from hope — mark it "unvalidated estimate" otherwise.
4. **Interrogate the results, don't obey them.** Highlight: top items that feel wrong to the user (the feeling usually encodes an unscored factor — surface it as a real criterion or let it go); items whose rank flips with a plausible input change (score fragility); dependency or time-window effects the formula missed. The output of scoring is a *conversation*, and the resolution gets written down.
5. **Build the Now/Next/Later roadmap** (`40-roadmap-now-next-later.md`), outcome-oriented:
   - **Now** = committed, specific, in flight or next up — phrased as problem/outcome with the solution attached.
   - **Next** = high-confidence direction, solution still flexible.
   - **Later** = themes and bets, explicitly subject to change.
   - Each row: item/outcome | strategic bet it serves | evidence strength (validated / partial / assumption) | success signal | **review date** — the date this bet gets re-examined against evidence; a bet without a review date is a feature promise. **Zombie-bet rule:** an item surviving two review cycles without new supporting evidence gets a discovery task or a kill decision, not a third quiet renewal. No delivery dates on Next/Later; if stakeholders demand dates, that's a Now-item conversation with delivery-planning.
6. **Write the rationale section** for stakeholders: the top 5 in ranked order with a one-sentence "why now," and — as important — the notable items NOT chosen and why. This paragraph prevents relitigating priorities every meeting.
7. **Route forward:** Now items with real complexity go to requirements-prd; simple ones straight to delivery-planning. Revisit the roadmap when metrics-iteration produces landing reviews.

## Artifact rules

Every artifact starts with `## TL;DR & So What` — **max 2 paragraphs, plain language**: (1) what's on top and what's deliberately not, (2) what that means for the next weeks and what would change the ordering.

## Pitfalls checklist

- [ ] Every scored item traces to a strategic bet; orphans were decided, not smuggled in.
- [ ] No false precision: scores presented as conversation-structure, tie-breaks acknowledged as judgment.
- [ ] Inputs weren't reverse-engineered to bless a pre-made decision (ask directly if the ranking "came out right").
- [ ] Confidence reflects evidence; pet projects don't get 100%.
- [ ] Roadmap rows are outcomes/problems, not a feature contract.
- [ ] No dates beyond Now. Public artifact carries a "subject to learning" note.
- [ ] Must-have inflation checked in MoSCoW (>60% Must = no real prioritization happened).
- [ ] The "not chosen and why" section exists.
