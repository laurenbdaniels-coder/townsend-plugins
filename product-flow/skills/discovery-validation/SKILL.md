---
name: discovery-validation
description: Guides customer discovery and problem validation — planning and running customer interviews, framing Jobs to Be Done, building opportunity solution trees, mapping and testing risky assumptions, and writing a validated problem statement. Use when the user has a product idea to validate, wants to prepare or synthesize customer interviews, asks "is this problem worth solving," mentions discovery, user research, problem validation, JTBD, or wants to test assumptions before building.
---

# Discovery & Validation (Stage 1)

Help the user find out whether the problem is real, who has it, and how they know — before anything gets built. Output is evidence, not opinion.

## Workspace protocol

Read `product-workspace/00-product-context.md` first (adapt depth to the user profile recorded there; if absent, ask up to 2 orienting questions and offer to run product-workflow-guide). Read any existing `10-discovery-*.md` to build on prior work. On re-runs or new initiatives, also read `80-metrics-*.md` (learning log, landing reviews) and `70-launch-learnings.md` — prior misses and customer verbatims are evidence and interview-question fodder. Save outputs to `product-workspace/10-discovery-<artifact>.md` (e.g., `10-discovery-interview-guide.md`, `10-discovery-assumption-map.md`, `10-discovery-problem-statement.md`) and update the Stage log in the context file. If no workspace exists and the user wants a quick one-off, proceed and offer to save at the end.


### Suite conventions (apply even when files are missing)

- Missing context or upstream artifacts never block: proceed anyway, ask at most 2 orienting questions in one round, tag unverified inherited claims `[ASSUMPTION]`, and offer to create a minimal `00-product-context.md` (product one-liner, user profile, authoring mode, stage log) when saving.
- Evidence discipline per this plugin's `standards/evidence-rules.md`: every claim gets a source line, an `[ASSUMPTION]` tag (stating what would confirm or kill it), or a `TK` placeholder — never an invented number, quote, or name. Stakeholder-bound docs surface open assumptions in their own section (tag-and-warn, never block).
- Before any gate or big commitment, run the door check from `standards/decision-frameworks.md`: two-way doors (reversible) get lightweight treatment; one-way doors (pricing, migrations, deprecations, public commitments) get the full gate.
- Stage log in `00-product-context.md` (create if absent): a table `| stage | artifact file | initiative | date | status |` — add or update your row whenever you save an artifact. Durable learnings file as INSIGHT-NNN entries in `85-insight-log.md`, the single cross-initiative memory (claim, source, confidence, implications, status; log within 48h; disconfirmed entries get marked and linked, never deleted).
- Repeat runs for a new feature/initiative: include an initiative slug in filenames — `NN-<stage>-<slug>-<artifact>.md` — and never overwrite another initiative's files. Product-level singletons (context, positioning, strategy, insight log) update in place with a dated changelog line at the bottom.
- Adapt depth to the user profile in the context file (ask once if unknown): solo founder → lightest artifact, minimum ceremony; team PM → emphasize alignment and decision rationale; learner → briefly explain why each step exists as you go. If authoring mode is `guide-only`, structure, question, and critique so the user writes the artifact themselves; if they still ask you to draft, nudge once toward their own words, then help fully — it's their product.
- One round of questions max before drafting; then proceed on documented `[ASSUMPTION]`s rather than interrogating.

## Framework menu — help them choose, don't lecture

Present the options relevant to their situation with one-line fit guidance; recommend one, but the user picks:

| Framework | What it is | Pick it when |
|---|---|---|
| **Mom Test interviewing** (Rob Fitzpatrick) | Interviewing discipline: talk about their life not your idea; ask about specific past events, never hypotheticals; listen 80%. | Always — this is the *technique* used inside any other choice. Default for early idea validation. |
| **Jobs to Be Done** (Christensen/Moesta) | Customers "hire" products to make progress; reconstruct the timeline of a real past purchase/switch and the forces acting on it (push, pull, anxiety, habit). | Entering or reframing a market; understanding why people switch; innovation beyond incremental features. |
| **Opportunity Solution Tree** (Teresa Torres) | Living tree: desired outcome → opportunities (needs/pains) → solutions → assumption tests; updated as interviews accumulate. | Ongoing team discovery tied to an outcome metric; you'll interview continuously, not as a one-off project. |
| **Assumption mapping & testing** | List assumptions behind the idea, plot by importance × evidence, test the riskiest with the cheapest experiment (interview, landing page, fake door, concierge). | Always as the closing move; especially pre-build when money/time is about to be committed. |

These stack rather than compete: Mom Test is the interviewing technique, JTBD is the lens for switching motivation, the tree is the ongoing operating system, assumption mapping is how discovery converts to decisions.

## Workflow

1. **Frame the outcome.** One sentence: "We believe [audience] struggles with [problem] when [context], and it's worth solving because [stakes]." This is the hypothesis discovery will confirm, reshape, or kill. Ask what evidence already exists (interviews done, support tickets, analytics, their own experience — flag "my own experience" as n=1).
2. **Choose from the menu** based on their situation; state your recommendation and why in two sentences.
3. **Produce the working artifacts** they need right now — typically:
   - **Interview guide**: build it from `references/interview-guide.md` — Mom Test question bank with JTBD forces framing, banned-questions list, recruiting screen, no-pitching rule, and the 48-hour note-capture template.
   - **JTBD job statements** if chosen: "When [situation], I want to [motivation], so I can [outcome]" + forces diagram per interview.
   - **Opportunity solution tree** if chosen: outcome at root, opportunities as *needs in the customer's words* (never solutions), candidate solutions beneath, assumption tests beneath those.
   - **Assumption map**: table of assumption | type (desirability/viability/feasibility) | importance (H/M/L) | current evidence (H/M/L) | cheapest test. Riskiest = high importance + low evidence; design tests for the top 2–3 only.
4. **Synthesize when they bring interview data** — use `references/synthesis-readout.md`: claim → source → confidence table (High = multiple independent sources; Low = uncited), counts stated ("6 of 8 mentioned…"), the mandatory "looked for and didn't find" section, and INSIGHT-NNN entries filed to `85-insight-log.md` within 48 hours. Never launder compliments into evidence; only past behavior and cost paid count.
5. **Write the validated problem statement** (`10-discovery-problem-statement.md`): the problem, who has it (specific segment, not "everyone"), evidence for (with counts and quotes), evidence against, what's still assumed, and a clear verdict — **validated / needs more evidence / invalidated** — with the reasoning.
6. **Close with the route forward:** validated → market-positioning (or straight to strategy-vision if the competitive picture is already clear); mixed → the 1–2 cheapest next tests; invalidated → congratulate them on cheap learning and offer to reframe the problem or pivot the segment.

## Artifact rules

Every artifact starts with `## TL;DR & So What` — **max 2 paragraphs, plain language**: (1) what we learned/built, (2) what it means and the next move. A non-PM reader must understand it.

## Pitfalls checklist (apply before saving)

- [ ] No hypothetical questions in interview guides ("would you use/pay for…") — past behavior only.
- [ ] Compliments and enthusiasm are not counted as validation anywhere.
- [ ] Opportunities are phrased as customer needs/pains, not disguised solutions.
- [ ] Disconfirming evidence is reported, not buried.
- [ ] Sample honesty: conclusions state n; 3 interviews ≠ "users want."
- [ ] The riskiest assumption has a test cheaper than building the product.
- [ ] If AI-synthesizing notes, the user is told to spot-check against raw notes — summaries can miss critical detail.
- [ ] "My own experience" or "everyone I talk to agrees" is flagged as founder bias, kindly.
