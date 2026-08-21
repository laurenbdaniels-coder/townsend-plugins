---
name: launch-gtm
description: Guides launch and go-to-market planning — assigning a launch tier by market impact, building a phased GTM checklist with owners, deriving a message house from positioning, and producing a launch brief with T-minus timeline and success metrics. Use when the user asks how to launch a product or feature, mentions go-to-market, GTM, launch plan, launch checklist, go/no-go decision, launch readiness, beta program or beta exit criteria, product marketing, announcement, release messaging, or "we're shipping soon, what now."
---

# Launch & GTM (Stage 7)

Help the user match launch effort to market impact and get the product into customers' hands with a message that lands. A launch is a beginning of adoption, not a finish line.

## Workspace protocol

Read `product-workspace/00-product-context.md`, `20-positioning-doc.md` (messaging is *derived* from positioning, never invented fresh at launch), `20-positioning-landscape.md` (alternatives' pricing for the pricing check), `50-requirements-*.md` (what was promised; success metrics), and `60-delivery-*.md` (what's shipping, when, and the open risks in the register). Save outputs as `product-workspace/70-launch-<artifact>.md` (`70-launch-brief.md`, `70-launch-checklist.md`, `70-launch-messaging.md`) and update the Stage log.


### Suite conventions (apply even when files are missing)

- Missing context or upstream artifacts never block: proceed anyway, ask at most 2 orienting questions in one round, tag unverified inherited claims `[ASSUMPTION]`, and offer to create a minimal `00-product-context.md` (product one-liner, user profile, authoring mode, stage log) when saving.
- Evidence discipline per this plugin's `standards/evidence-rules.md`: every claim gets a source line, an `[ASSUMPTION]` tag (stating what would confirm or kill it), or a `TK` placeholder — never an invented number, quote, or name. Stakeholder-bound docs surface open assumptions in their own section (tag-and-warn, never block).
- Before any gate or big commitment, run the door check from `standards/decision-frameworks.md`: two-way doors (reversible) get lightweight treatment; one-way doors (pricing, migrations, deprecations, public commitments) get the full gate.
- Stage log in `00-product-context.md` (create if absent): a table `| stage | artifact file | initiative | date | status |` — add or update your row whenever you save an artifact. Durable learnings file as INSIGHT-NNN entries in `85-insight-log.md`, the single cross-initiative memory (claim, source, confidence, implications, status; log within 48h; disconfirmed entries get marked and linked, never deleted).
- Repeat runs for a new feature/initiative: include an initiative slug in filenames — `NN-<stage>-<slug>-<artifact>.md` — and never overwrite another initiative's files. Product-level singletons (context, positioning, strategy, insight log) update in place with a dated changelog line at the bottom.
- Adapt depth to the user profile in the context file (ask once if unknown): solo founder → lightest artifact, minimum ceremony; team PM → emphasize alignment and decision rationale; learner → briefly explain why each step exists as you go. If authoring mode is `guide-only`, structure, question, and critique so the user writes the artifact themselves; if they still ask you to draft, nudge once toward their own words, then help fully — it's their product.
- One round of questions max before drafting; then proceed on documented `[ASSUMPTION]`s rather than interrogating.

## Framework menu

| Framework | What it is | Pick it when |
|---|---|---|
| **Launch tiering** | Classify by *market impact* — does it change buying decisions, open new segments, shift competitive position, need market education? Tier 1: company-defining, full multi-channel push (1–2×/year max). Tier 2: meaningful to specific segments — targeted campaign. Tier 3: incremental — changelog, docs, in-app note. Solo founders: default to Tier 2 or below — the checklist collapses to announcement + tracking + landing review. | Always — this is the first decision; everything else scales from it. |
| **Phased GTM checklist** | Five phases: research readiness → strategy & positioning → sales/marketing setup → content & enablement → launch & measure. | Tier 1–2 launches, especially B2B or new-market entries. |
| **Message house** | Master narrative (roof) + 3–4 pillar messages + proof points under each, built from the positioning doc and tested against customer language. | Tier 1–2 launches and any repositioning; skip for Tier 3. |

## Workflow

1. **Assign the tier — by market impact only.** Engineering effort and internal excitement are explicitly not criteria; a two-year replatform can be Tier 3 and a two-week feature Tier 1. Ask: change buying decisions? new personas/market? competitive/positioning shift? revenue protected or created? education needed? Mostly-no → Tier 3: write the changelog entry, notify affected users, done — congratulate the user on NOT over-launching. Record the tier and reasoning.
2. **Define launch success now, not after.** From the PRD's success metrics (if none were pre-registered upstream, set them now with the user and label them as defined-at-launch): 2–3 adoption/behavior targets (e.g., "X% of target segment activates within 30 days"), plus a measurement owner and a **landing review date** (2–6 weeks post-launch) booked in advance. Shipping is not success; behavior change is.
3. **Build the message house** (Tier 1–2): roof = one-sentence master narrative from the positioning statement; pillars = 3–4 claims that matter to the best-fit segment; proof under each = demo, number, quote, comparison. Test: does it use words from discovery interviews? Would the primary competitive alternative's marketing sound different, or could they ship the same page?
4. **Build the phased checklist** (`70-launch-checklist.md`) scaled to tier, every item with a DRI (directly responsible individual) and date:
   - *Readiness:* ICP confirmed against the positioning doc's best-fit segment — divergence means a positioning refresh, not a quiet widening; pricing/packaging decided — if it isn't, anchor on the value delivered (positioning doc), check what the teardown says alternatives charge, default to simple (2–3 tiers), and treat the first price as a test with a review date; support & docs ready; legal/compliance cleared — flagged early: personal data, payments, minors, health/financial data, or a new jurisdiction means review at PRD time, not launch week; sales/CS trained (B2B); feedback channel open.
   - *Ops readiness:* monitoring/alerts live on the new surface, a known-issues list + escalation path handed to support, and the rollback owner from delivery-planning named and reachable on launch day.
   - *Assets:* announcement, landing/docs updates, demo, enablement kit (one-pager, FAQ, objection handling) — scaled to tier.
   - *Sequencing:* internal → (optionally) beta/early access per `references/beta-exit.md` (justification, pre-committed exit criteria including the blocking threshold, and the improve/hold/sunset branches decided in advance) → public. T-minus timeline: T-14 internal announce & training, T-7 assets frozen, T-1 go/no-go per `references/go-no-go.md` (door check first — two-way doors get the lightweight path; readiness table with named sign-offs, rollback row, AI-quality row for generative features, landing review booked at the gate), T-0 launch, T+7 first read, T+30 landing review.
   - *Measurement:* every event in the tracking plan verified firing BEFORE launch day (attribution retrofitted after launch is folklore); day-1 watch: dashboard open, event volumes sane, rollback criteria at hand.
5. **Write the launch brief** (`70-launch-brief.md`): tier + reasoning, audience, the one-line message, channels, timeline, owners, success targets + review date, top 3 launch risks — check `60-delivery-risk-register.md` first and carry forward any open risk that survives into market exposure, then add launch-specific ones (low awareness in segment, support load, competitor response) — with mitigations.
6. **Plan the follow-through.** Adoption work weeks 1–4: activation nudges for the target segment, watch-and-respond on feedback channels, a "week-2 friction" review of onboarding drop-off. Log all of it — feedback-channel themes, friction findings, objections and questions — in `70-launch-learnings.md` (dated); that file is the qualitative sink metrics-iteration and future discovery/positioning runs read. Promote durable findings to INSIGHT-NNN entries in `85-insight-log.md`. Launch fatigue warning: if everything is announced loudly, the market learns to ignore you — protect Tier 1 credibility.
7. **Route forward:** hand success targets and review date to metrics-iteration for the landing review. Capture real objections/questions from launch in `70-launch-learnings.md` (dated) — and if they contradict the positioning, recommend a refresh via market-positioning rather than silently editing upstream docs.

## Artifact rules

Every artifact starts with `## TL;DR & So What` — **max 2 paragraphs, plain language**: (1) what's launching, at what tier, to whom, with what message, (2) what success looks like by when, and the biggest risk to watch.

## Pitfalls checklist

- [ ] Tier assigned by market impact; effort/excitement explicitly rejected as criteria.
- [ ] Tier 3 work stayed Tier 3 (no over-launching).
- [ ] Messaging derived from the positioning doc and discovery language, not invented on launch week.
- [ ] Every checklist item has a named DRI and date.
- [ ] Success = behavior targets with a booked landing review, not "we shipped."
- [ ] Tracking/attribution verified pre-launch.
- [ ] Go/no-go criteria written before launch day.
- [ ] Post-launch adoption plan exists (launch ≠ finish line).
