---
name: market-positioning
description: Guides competitive analysis, market sizing, and product positioning — mapping real competitive alternatives, building TAM/SAM/SOM estimates, assessing industry forces, and producing a positioning document and battle cards. Use when the user asks about competitors, competitive analysis, market size, differentiation, positioning, "who else does this," "how big is this market," target segments, choosing a beachhead or wedge market, willingness to pay, business viability of a direction, or how to explain why their product wins.
---

# Market & Positioning (Stage 2)

Help the user understand the landscape they're entering and articulate where they win. Output: an honest competitive picture and a positioning document a teammate or investor could repeat back.

## Workspace protocol

Read `product-workspace/00-product-context.md` and `10-discovery-*.md` first — the validated problem statement and segment define whose alternatives matter. If discovery artifacts are missing, note which claims below rest on assumption rather than evidence. On refresh/re-runs, also read `70-launch-learnings.md` and recent `80-metrics-*.md` — real objections, win/loss themes, and funnel behavior are positioning evidence. Save outputs as `product-workspace/20-positioning-<artifact>.md` (`20-positioning-landscape.md`, `20-positioning-market-size.md`, `20-positioning-doc.md`) and update the Stage log.


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
| **Dunford positioning** (April Dunford, five components) | Competitive alternatives → unique attributes → value enabled → best-fit segments → market category. Sequenced — each step feeds the next. | Default for the positioning doc itself; essential for B2B, post-pivot, or "prospects seem confused" symptoms. |
| **TAM/SAM/SOM sizing** | Total → serviceable → obtainable market, built top-down (analyst numbers) AND bottom-up (price × reachable buyers). Bottom-up is the credible half. | Business cases, fundraising, choosing which segment deserves focus. |
| **Porter's Five Forces** | Industry attractiveness via rivalry, entrants, substitutes, buyer power, supplier power. | Category-level bets: entering a new market, pricing power questions, build-vs-enter. Skip for feature-level work. |
| **Competitive teardown & battle cards** | Structured competitor matrix (features, pricing, wedge, win/loss themes) distilled into per-competitor cards. | Contested categories, sales-led motions, or whenever "how do we beat X" comes up repeatedly. |

Most users need Dunford + a light teardown; add sizing when money is being raised or allocated, Porter only for category-level strategy.

## Workflow

1. **Anchor on the segment** from discovery. Positioning is for a specific best-fit customer, not the whole world. If discovery gave no segment, help define one now (and mark it assumed).
2. **List competitive alternatives the customer actually sees** — including "do nothing," "spreadsheet + intern," and adjacent workarounds. This is Dunford's step one and where most positioning goes wrong: the real competitor is often the status quo, not the lookalike startup. Use web search if available to verify the landscape is current; cite what you find.
3. **Build the teardown** (if chosen): matrix of alternative | who picks it | why they pick it (their words if discovery has quotes) | pricing | where it's weak for our segment. Derive battle cards only for the 2–3 that come up in real deals/conversations.
4. **Extract unique attributes → value.** What does this product have that the alternatives don't (features, model, data, distribution, founder insight)? For each, translate attribute → so-what value for the best-fit segment. Attributes without a value translation get cut, not padded. Write each surviving differentiator as an **insight → data → implication** triplet — the claim about why it matters to this segment, the sourced evidence, and what it lets customers do that alternatives can't; these triplets feed strategy-vision's why-case (why this / why us / why now) directly.
5. **Choose the market category** that makes the value obvious fastest — usually an existing category with a twist; creating a new category is a costly last resort, say so.
6. **Size the market** (if chosen): top-down for the headline, bottom-up for credibility (identifiable buyers × realistic price × plausible share, with each input sourced or flagged as a guess). Present the two side by side; if they disagree wildly, the bottom-up number wins.
7. **Assess forces** (if chosen): one paragraph per force, ending in a verdict — attractive / neutral / hostile — and the single force that most constrains strategy.
8. **Score wedges and check viability when choosing between entry points** — use `references/wedge-viability.md`: the wedge scorer (2–4 candidate segments × use cases, evidence-cited scores where an uncited score auto-drops to Low confidence, disconfirming check, one beachhead selected with a review date) and the viability check (pricing anchored to observed spend, sell-test through the real channel, channel economics, complement-or-cannibalize with a one-way-door flag).
9. **Write the positioning doc** (`20-positioning-doc.md`): the five Dunford components in order, each 2–4 sentences, plus a one-line positioning statement ("For [segment] who [need], [product] is the [category] that [key value], unlike [primary alternative].") and open risks.
10. **Route forward:** positioning feeds strategy-vision (category + segment choices are strategy inputs) and later launch-gtm (messaging is built *from* this doc, not invented at launch).

## Artifact rules

Every artifact starts with `## TL;DR & So What` — **max 2 paragraphs, plain language**: (1) the landscape/position in a nutshell, (2) what it means for what we do next.

## Pitfalls checklist

- [ ] "Do nothing"/status quo appears in the alternatives list.
- [ ] Positioning targets a best-fit segment, not "anyone who…".
- [ ] No new-category creation without acknowledging the education cost.
- [ ] Every claimed differentiator survives "can the top 2 alternatives say the same sentence?"
- [ ] Market size includes a bottom-up calculation; no naked "1% of $50B."
- [ ] Competitor facts are dated (markets move); note when each was checked.
- [ ] Positioning was tested against discovery quotes — does it use words customers used?
- [ ] Honest section on where alternatives are genuinely better.
- [ ] Differentiators without adequate proof are listed as risks, not claims.
