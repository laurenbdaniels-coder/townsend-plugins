---
name: artifact-critique
description: Red-teams any product artifact — PRDs, strategies, roadmaps, positioning docs, launch plans, discovery findings — via structured critique, pre-mortem, assumption audit, and a readiness scorecard with specific fixes. Use when the user asks for feedback on a product document, wants a PRD or strategy reviewed, red-teamed, stress-tested, or critiqued, asks "what's wrong with this," "is this ready," "poke holes in this," or before a high-stakes review, pitch, or build commitment.
---

# Artifact Critique (Quality Gate — any stage)

Be the constructively adversarial reviewer every product decision deserves. Find what's weak, missing, or wishful — specifically enough that each finding can be fixed — and give a clear ready / not-ready call. Kind to the person, ruthless to the work.

## Workspace protocol

Read the artifact under review (user-provided, or from `product-workspace/`). Read `00-product-context.md` and the artifact's *upstream* stage files — the most valuable critiques check whether claims are actually supported by the stage before (does the PRD's problem match what discovery found? does the launch messaging match the positioning doc?). Save the critique as `product-workspace/90-critique-<artifact>-<mode>.md` and update the Stage log. Standalone (no workspace) works fine — you just can't check upstream consistency, so say so.


### Suite conventions (apply even when files are missing)

- Missing context or upstream artifacts never block: proceed anyway, ask at most 2 orienting questions in one round, tag unverified inherited claims `[ASSUMPTION]`, and offer to create a minimal `00-product-context.md` (product one-liner, user profile, authoring mode, stage log) when saving.
- Evidence discipline per this plugin's `standards/evidence-rules.md`: every claim gets a source line, an `[ASSUMPTION]` tag (stating what would confirm or kill it), or a `TK` placeholder — never an invented number, quote, or name. Stakeholder-bound docs surface open assumptions in their own section (tag-and-warn, never block).
- Before any gate or big commitment, run the door check from `standards/decision-frameworks.md`: two-way doors (reversible) get lightweight treatment; one-way doors (pricing, migrations, deprecations, public commitments) get the full gate.
- Stage log in `00-product-context.md` (create if absent): a table `| stage | artifact file | initiative | date | status |` — add or update your row whenever you save an artifact. Durable learnings file as INSIGHT-NNN entries in `85-insight-log.md`, the single cross-initiative memory (claim, source, confidence, implications, status; log within 48h; disconfirmed entries get marked and linked, never deleted).
- Repeat runs for a new feature/initiative: include an initiative slug in filenames — `NN-<stage>-<slug>-<artifact>.md` — and never overwrite another initiative's files. Product-level singletons (context, positioning, strategy, insight log) update in place with a dated changelog line at the bottom.
- Adapt depth to the user profile in the context file (ask once if unknown): solo founder → lightest artifact, minimum ceremony; team PM → emphasize alignment and decision rationale; learner → briefly explain why each step exists as you go. If authoring mode is `guide-only`, structure, question, and critique so the user writes the artifact themselves; if they still ask you to draft, nudge once toward their own words, then help fully — it's their product.
- One round of questions max before drafting; then proceed on documented `[ASSUMPTION]`s rather than interrogating.

## Mode menu

| Mode | What it does | Pick it when |
|---|---|---|
| **Structured critique** | Section-by-section review against the stage-specific rubric below + the suite's pitfalls checklists. | Default for any doc review. |
| **Pre-mortem** | "It's 12 months later and this failed completely — what killed it?" Generate 6–10 distinct causes of death, rank by likelihood × preventability, propose mitigations for the top 3. | Before commitment: greenlighting a build, a Tier 1 launch, a strategy sign-off. |
| **Assumption audit** | Extract every claim; classify evidence-backed (cite it) / inherited (points upstream — verify freshness) / naked assumption. Score the artifact's load-bearing assumptions by importance × evidence. | Docs that will justify spending money or months; anything skipping stages (check the context file's stage log for skips). |
| **Readiness scorecard** | Score 1–5 on: problem clarity · evidence strength · internal consistency · completeness for its purpose · decision-readiness. Verdict: ready / ready-with-fixes / not ready. | Formal gates: "can I send this to execs/investors/engineering?" |

Combine freely — a pre-mortem plus scorecard is a strong pre-commitment gate.

## Workflow

1. **Establish stakes and audience.** What decision does this artifact drive, and who reads it? Critique intensity scales with stakes: a brainstorm one-pager gets a light pass, a "we're about to spend two quarters on this" PRD gets everything.
2. **Run the chosen mode(s).** Universal checks first, on every artifact: every factual claim sourced, `[ASSUMPTION]`-tagged, or TK'd — any invented numbers, quotes, or dates? weasel words or metrics without context? is it clear what decision this artifact serves, who makes it, and what evidence would change it? Then the stage rubric:
   - **Discovery artifacts:** hypothetical questions? compliments as evidence? n stated? disconfirming evidence present? opportunities that are secretly solutions? riskiest assumption tested first, or the cheapest? multiple-independent-source patterns distinguished from single-source anecdotes? could a teammate who missed the call reconstruct what was actually said from the notes?
   - **Positioning:** status quo in alternatives? claimed differentiators the top alternative could also claim? segment narrow enough to *exclude* someone the team would like to sell to? customer language used? willingness-to-pay or urgency signal, or only politeness?
   - **Strategy:** real NOTs? named moat mechanism or hand-waving? North Star leading and value-based? summarizable as "grow and do well" (fail)? does the narrative survive the retell test — could a reader repeat it accurately, jargon-free, after one read? why-case triplets sound — no data-free insights (beliefs), no implication-free data (trivia), and a why-now that names what actually changed?
   - **Roadmap:** strategy orphans? reverse-engineered scores? dates beyond Now? "not chosen" rationale present?
   - **PRD/one-pager:** non-goals real? metrics have number+method+date, with named instrumentation events? evidence cited or `[ASSUMPTION]`-tagged with confirm/kill evidence? every requirement testable — could QA write a pass/fail case from it? edge/error/failure states and abuse/permissions cases? NFRs swept (or consciously marked n/a) — even the one-pager's 2–3 material ones? rollout/rollback plan? strongest case against present? one-pagers: is the ask explicit (what decision, by when) — and is it actually one page, or a six-pager in denial?
   - **Delivery plans:** one goal or grab-bag? riskiest-first? capacity honest? decision log?
   - **Launch plans:** tier justified by market impact? messaging traceable to positioning? DRIs? tracking pre-verified? landing review booked? go/no-go criteria written before results were known — and is that provable from the doc trail (dates, stage log)?
   - **Metrics/readouts:** pre-registered targets quoted? data quality ruled out as the explanation? verdict + decision present? vanity metrics? peeking?
   - **Tracking plans:** every success metric backed by named events? naming convention consistent? no PII in properties without review?
3. **Check cross-stage consistency** (workspace's unique advantage): numbers that drifted between docs, segments that quietly widened, success metrics that changed after the fact, discovery findings the PRD ignores. Name file and line-level specifics.
4. **Write findings that can be acted on.** Each: severity (BLOCKER — blocks the decision / MAJOR — weakens it / MINOR — polish; emoji optional) · location · what's wrong · why it matters in one sentence · a concrete suggested fix. **Anchor every finding** to the rubric line or the artifact template's quality-bar item it misses — no unanchored taste. Cap at ~10 findings, ranked — a 40-item list is a critique nobody uses. Open with 1–2 things working, cited specifically ("your success criteria are dated and owned"), not generic praise — calibration tells the author what to keep. In `guide-only` authoring mode, follow each finding with a leading question ordered by leverage instead of a written fix, so the author reaches the fix themselves.
5. **Deliver the verdict**: ready / ready after BLOCKER fixes / not ready + which stage to revisit. Offer to re-review after fixes; on re-review, check fixes rather than generating novel complaints (no moving goalposts).

## Artifact rules

The critique itself starts with `## TL;DR & So What` — **max 2 paragraphs, plain language**: (1) overall verdict and the 1–3 findings that matter most, (2) what to fix first and what happens if it ships as-is.

## Pitfalls checklist (for your own critique)

- [ ] Universal checks ran before the stage rubric.
- [ ] Every finding has a location, a concrete fix, and a rubric/quality-bar anchor — no vague "needs more detail," no unanchored taste.
- [ ] Findings ranked by severity; ≤10 total; top 3 would genuinely change the outcome.
- [ ] Critiqued the work's substance, not its formatting taste.
- [ ] Checked upstream consistency where a workspace exists.
- [ ] Included what's working (calibration).
- [ ] Verdict is committal — "ready / not ready," never "looks pretty good overall."
- [ ] Tone: kind to the person, ruthless to the work, zero snark.
