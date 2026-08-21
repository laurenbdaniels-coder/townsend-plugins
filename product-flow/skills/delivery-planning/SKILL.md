---
name: delivery-planning
description: Guides delivery planning and execution hygiene — choosing between Scrum sprints, Kanban flow, or Shape Up cycles, writing sprint goals and Shape Up pitches, building risk registers, and setting a stakeholder communication cadence with status updates and decision logs. Use when the user asks about sprint planning, delivery or release planning, agile process choice, Shape Up, managing engineering execution as a PM, writing a delivery or build status update for stakeholders, keeping stakeholders informed during a build, planning pre-launch testing or UAT, writing a test plan, or setting quality evals for an AI/LLM-powered feature.
---

# Delivery Planning (Stage 6)

Help the user get the thing built predictably: pick a delivery rhythm that fits the team, plan the first increment well, and run the communication that keeps stakeholders calm and decisions unstuck.

## Workspace protocol

Read `product-workspace/00-product-context.md`, `50-requirements-*.md` (the spec and stories being delivered), and `40-roadmap-*.md` first. Save outputs as `product-workspace/60-delivery-<artifact>.md` (`60-delivery-plan.md`, `60-delivery-risk-register.md`, `60-delivery-comms.md`) and update the Stage log.


### Suite conventions (apply even when files are missing)

- Missing context or upstream artifacts never block: proceed anyway, ask at most 2 orienting questions in one round, tag unverified inherited claims `[ASSUMPTION]`, and offer to create a minimal `00-product-context.md` (product one-liner, user profile, authoring mode, stage log) when saving.
- Evidence discipline per this plugin's `standards/evidence-rules.md`: every claim gets a source line, an `[ASSUMPTION]` tag (stating what would confirm or kill it), or a `TK` placeholder — never an invented number, quote, or name. Stakeholder-bound docs surface open assumptions in their own section (tag-and-warn, never block).
- Before any gate or big commitment, run the door check from `standards/decision-frameworks.md`: two-way doors (reversible) get lightweight treatment; one-way doors (pricing, migrations, deprecations, public commitments) get the full gate.
- Stage log in `00-product-context.md` (create if absent): a table `| stage | artifact file | initiative | date | status |` — add or update your row whenever you save an artifact. Durable learnings file as INSIGHT-NNN entries in `85-insight-log.md`, the single cross-initiative memory (claim, source, confidence, implications, status; log within 48h; disconfirmed entries get marked and linked, never deleted).
- Repeat runs for a new feature/initiative: include an initiative slug in filenames — `NN-<stage>-<slug>-<artifact>.md` — and never overwrite another initiative's files. Product-level singletons (context, positioning, strategy, insight log) update in place with a dated changelog line at the bottom.
- Adapt depth to the user profile in the context file (ask once if unknown): solo founder → lightest artifact, minimum ceremony; team PM → emphasize alignment and decision rationale; learner → briefly explain why each step exists as you go. If authoring mode is `guide-only`, structure, question, and critique so the user writes the artifact themselves; if they still ask you to draft, nudge once toward their own words, then help fully — it's their product.
- One round of questions max before drafting; then proceed on documented `[ASSUMPTION]`s rather than interrogating.

## Framework menu

| Method | Rhythm | Pick it when |
|---|---|---|
| **Scrum** | Fixed sprints (1–4 wks): planning (goal → backlog selection → decomposition), daily sync, review/demo, retrospective. | Team wants predictable cadence and demo rhythm; requirements evolve; stakeholders need regular checkpoints. |
| **Kanban** | Continuous flow, WIP limits, cycle-time tracking; no fixed iterations. | Interrupt-heavy or ops-flavored work, continuous deployment, teams where sprint batching adds ceremony without value. |
| **Shape Up** | 6-week cycles + 2-week cooldown. Work is "shaped" into pitches (problem, appetite, rough solution, rabbit holes, no-gos) before a betting table commits; unfinished work doesn't auto-extend. | Small senior teams, feature-factory fatigue, orgs able to protect uninterrupted focus. Poor fit: heavy cross-team dependencies, junior-heavy teams. |

Solo founder building alone? Skip ceremony: a weekly goal + Kanban-style WIP limit of 1–2 is usually the honest answer — say so.

## Workflow

1. **Pick the rhythm** from the menu based on team size, seniority, interrupt load, and dependency structure. Two-sentence recommendation, user decides.
2. **Plan the first increment:**
   - **Scrum:** write a real **sprint goal** — one outcome sentence a stakeholder would care about, not a ticket list. Select stories that serve it (from `50-requirements-*`), sized to demonstrated capacity minus interrupts, not to ambition. Define "done" explicitly (tested? flagged? documented? demo-able? tracking-plan events firing and spot-checked in staging?).
   - **Shape Up:** write the **pitch**: problem (with evidence link), **appetite** ("this is worth 6 weeks, no more" — appetite replaces estimation), rough solution sketched at breadboard level, rabbit holes called out, explicit no-gos.
   - **Kanban:** define the board columns, WIP limits, and the policy for what may enter "in progress."
3. **Sequence for risk, not comfort.** Identify the riskiest/least-known slice (new integration, unproven tech, the thing nobody has done before) and schedule it *first*, thinnest-possible end-to-end. Walking skeleton beats polished corner.
4. **Build the risk register** (`60-delivery-risk-register.md`): risk | likelihood | impact | early warning signal | mitigation | owner. Seed it from the PRD's Risks & mitigations first — carry over every still-open risk, marked *inherited* — then add the delivery-specific ones. Include the unglamorous ones: key-person dependency, unclear requirement sections (link them), external/API dependencies, scope pressure. Review cadence: weekly, 5 minutes, at the top of planning.
5. **Set the stakeholder communication system** (`60-delivery-comms.md`):
   - Map stakeholders: who decides, who's consulted, who's informed (a simple power/interest tiering is enough).
   - **Weekly async status** template: GREEN/YELLOW/RED headline (emoji optional; colors follow the strict definitions in metrics-iteration's goal-status reference — yellow requires a credible path to green, no path means red) · progress (outcomes, not activity) · risks & changes since last week · **decisions needed, from whom, by when**. Rule: bad news travels *first* — a surfaced risk is a plan, a hidden risk is a crisis.
   - **Decision log**: date | decision | options considered | who decided | rationale. This kills relitigating.
6. **Protect the goal during execution.** Mid-sprint/cycle additions trade explicitly against the goal ("yes, and which of these leaves?"). Track scope changes in the status update so the trend is visible.
7. **Validate before launch takes over.** As the build nears shippable, produce the validation plan from `references/validation-plan.md` — pass/fail bar pre-committed before testing starts, functional coverage traced to the PRD (unhappy paths, permissions, tracking events), and persona-based UAT with real target-segment testers. **AI/generative features additionally require the eval plan** in `references/ai-eval.md` (quality dimensions, golden set, pre-committed ship bar, drift monitoring) — deterministic pass/fail testing doesn't cover non-deterministic outputs.
8. **Write the rollout plan before code complete**, with engineering: behind a feature flag? staged rollout (internal → small % → 100%) with promotion criteria between steps? And the reverse gear — a rollback trigger ("if [metric] degrades by [X] within [Y], we roll back"), who owns that decision, and how fast the kill-switch works. Agree the hotfix path too: who ships an emergency fix, and how fast. A launch you can't undo is a bet, not a rollout.
9. **Close each increment with a retro** (what to keep / drop / try — 3 items max, one actually adopted) and **route forward**: as the build nears shippable, start launch-gtm — launch planning begins *before* code complete, not after.

## Artifact rules

Every artifact starts with `## TL;DR & So What` — **max 2 paragraphs, plain language**: (1) what's being delivered, in what rhythm, and current health, (2) the top risk or needed decision and what happens if it's ignored.

## Pitfalls checklist

- [ ] Sprint/cycle has ONE goal sentence, not a grab-bag of tickets.
- [ ] Capacity based on demonstrated throughput, not optimism; estimates are not promises.
- [ ] Riskiest slice scheduled first, end-to-end.
- [ ] Definition of done written before work starts.
- [ ] Status updates lead with risks and needed decisions, not activity lists.
- [ ] Decision log exists and is used; no decision made twice.
- [ ] Rollout plan has a rollback trigger with a named owner; the kill-switch was tested, not assumed.
- [ ] Shape Up: nothing bet on that isn't shaped; appetite respected (no auto-extension).
- [ ] PM is acting as outcome owner, not ticket administrator — if every conversation is about tickets, flag it.
