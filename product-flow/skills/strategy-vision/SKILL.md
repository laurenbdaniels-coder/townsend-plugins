---
name: strategy-vision
description: Guides product vision and strategy — writing a product vision, making explicit where-to-play and how-to-win choices, testing for durable advantage, and defining a North Star metric with input metrics. Use when the user asks about product strategy, vision, mission for a product, "what should our strategy be," long-term direction, differentiation strategy, choosing a North Star metric, or aligning a team on where the product is going.
---

# Strategy & Vision (Stage 3)

Help the user make actual choices — what game to play, how to win it, and how they'll know. Strategy is choices with tradeoffs, not a goals list or a feature list.

## Workspace protocol

Read `product-workspace/00-product-context.md`, `10-discovery-problem-statement.md`, and `20-positioning-doc.md` first — segment, category, and differentiation choices are strategy raw material. Flag anything below that rests on missing upstream work. On revisits, also read `80-metrics-*.md` (landing reviews, learning log) — shipped results are the standing test of the current strategy. Save outputs as `product-workspace/30-strategy-<artifact>.md` (`30-strategy-vision.md`, `30-strategy-onepager.md`, `30-strategy-northstar.md`) and update the Stage log.


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
| **Product Vision Board** (Roman Pichler) | One page: vision statement + target group + needs + key product differentiators + business goals. | Kicking off a new product; fast stakeholder alignment; solo founders who need direction without a strategy offsite. |
| **Playing to Win** (Lafley & Martin) | Five cascading choices: winning aspiration → where to play → how to win → capabilities needed → management systems. | Company- or portfolio-level strategy; forcing real tradeoffs; the antidote to "our strategy is our goals." |
| **DHM** (Gibson Biddle) | Strategy = ways the product **D**elights customers, in **H**ard-to-copy ways (network effects, brand, switching costs, counter-positioning, unique data), with healthy **M**argin. | Testing whether a strategy is durable; consumer and scale-up products; "why won't a big player copy this?" |
| **North Star framework** (popularized by Amplitude) | One leading-indicator metric capturing value delivered to customers, decomposed into 3–5 input metrics teams can move. | Connecting strategy to daily work; aligning multiple teams; pairs with any of the above. |

Typical combos: solo founder → Vision Board + North Star. Team PM at company scale → Playing to Win (or Vision Board) + DHM check + North Star. DHM is a *test* applied to any strategy, not a standalone doc.

## Workflow

1. **Vision first, briefly.** 1–3 sentences, 3–10 year horizon: the change in the world / customer's life if this fully works. Test: does it exclude anything? A vision nothing could contradict is a slogan. Keep it stable; strategy beneath it can change.
2. **Build the why-case: Insight → Data → Implication.** The rationale for the product is 2–4 load-bearing insights, each written as a triplet: the **insight** (a falsifiable claim about the customer, market, or timing — solution-free), the **data** behind it (source lines per `standards/evidence-rules.md`; pull rows from `85-insight-log.md` and the discovery synthesis — INSIGHT-NNN entries are pre-made for this), and the **implication** (what this means we should do — the bridge from evidence to choice). Together the implications must answer three questions: **why this product** (the unmet-job insight), **why us vs. others** (the unfair-advantage or alternatives'-blind-spot insight, from positioning), and **why now** (the timing insight — what changed in the world: technology, regulation, behavior, cost curve — that makes this newly possible or newly urgent; if nothing changed, the "why hasn't someone already done this" question is coming, so answer it). An insight with no data is a belief — tag it `[ASSUMPTION]`; data with no implication is trivia — cut it.
3. **Make the choices** (structure per chosen framework):
   - Where to play: which segment (from positioning), which use cases, which channels — and explicitly what we are NOT playing for.
   - How to win: the value + cost/experience wedge vs. the alternatives; from positioning's unique attributes.
   - Run the **DHM test** on the result: What delights? What's hard to copy — name the specific moat and be skeptical (features are not moats). How does margin work — even roughly?
   - Capabilities & systems (Playing to Win): what must be true operationally; what we must build or hire that we don't have.
4. **Force the tradeoff conversation.** For every choice, write the road not taken and why. If the user can't name what they're giving up, the choice isn't made yet — say so kindly and help them make it.
5. **Define the North Star** (if chosen): one metric that (a) measures value customers *receive* (not vanity — not raw signups, not revenue, which lags), (b) leads the business results, (c) teams can influence weekly. Decompose into 3–5 input metrics (breadth, depth, frequency, efficiency style). Sanity-check: "if this number doubled but nothing else changed, would the business really be healthier?" Save it as `30-strategy-northstar.md` (metric, definition, inputs, measurement source) — metrics-iteration reads this file later.
6. **Write the strategy one-pager** (`30-strategy-onepager.md`): vision, the why-case (2–4 insight → data → implication triplets answering why this / why us / why now), where-to-play/how-to-win choices with the explicit NOTs, DHM verdict, North Star + inputs, top 3 strategic risks, and the 2–3 near-term bets the strategy implies (these seed the roadmap).
7. **Route forward:** roadmap-prioritization uses the bets and North Star inputs as its strategy filter — items that serve no strategic bet shouldn't even enter scoring.

## Artifact rules

Every artifact starts with `## TL;DR & So What` — **max 2 paragraphs, plain language**: (1) the strategy in a nutshell — the game and the wedge, (2) what it commits us to do and stop doing next.

## Pitfalls checklist

- [ ] Strategy contains explicit "we will NOT" statements.
- [ ] Vision ≠ roadmap ≠ mission; each stated once, at its own altitude.
- [ ] The hard-to-copy claim names a real moat mechanism, not "we'll execute better."
- [ ] North Star is a leading indicator of customer value, not revenue or MAU.
- [ ] Every strategic bet traces to segment/positioning evidence — or is flagged as a belief.
- [ ] Why-case triplets complete: no data-free insights (beliefs — tag them), no implication-free data (trivia — cut it), and the why-now names what actually changed.
- [ ] Strategy fits on one page; if it needs ten, choices are missing.
- [ ] A skeptical exec could not summarize this as "grow, do a good job, and win."
