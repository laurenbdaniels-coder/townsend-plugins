---
name: requirements-prd
description: Guides writing product requirements at the right weight — Lean Canvas for unvalidated business ideas, Amazon-style PR-FAQ for big bets, lean one-pagers and full PRDs for features, and user stories with Given/When/Then acceptance criteria for delivery. Use when the user asks for a PRD, spec, product requirements, one-pager, press release/FAQ, user stories, acceptance criteria, or says "write up what we're building" or "turn this idea into a spec."
---

# Requirements & PRD (Stage 5)

Help the user write down what exactly is being built and why — at the lightest weight that creates alignment. The document is a thinking tool first, contract never.

## Workspace protocol

Read `product-workspace/00-product-context.md`, `10-discovery-problem-statement.md`, `10-discovery-assumption-map.md` (open risky assumptions), `20-positioning-doc.md` (target user and segment), `30-strategy-onepager.md`, and `40-roadmap-*.md` first — a PRD's problem/evidence/metrics sections should be *inherited*, not reinvented. Quote discovery evidence directly where it exists; where it doesn't, tag the claim `[ASSUMPTION]`. Save outputs as `product-workspace/50-requirements-<artifact>.md` and update the Stage log.


### Suite conventions (apply even when files are missing)

- Missing context or upstream artifacts never block: proceed anyway, ask at most 2 orienting questions in one round, tag unverified inherited claims `[ASSUMPTION]`, and offer to create a minimal `00-product-context.md` (product one-liner, user profile, authoring mode, stage log) when saving.
- Evidence discipline per this plugin's `standards/evidence-rules.md`: every claim gets a source line, an `[ASSUMPTION]` tag (stating what would confirm or kill it), or a `TK` placeholder — never an invented number, quote, or name. Stakeholder-bound docs surface open assumptions in their own section (tag-and-warn, never block).
- Before any gate or big commitment, run the door check from `standards/decision-frameworks.md`: two-way doors (reversible) get lightweight treatment; one-way doors (pricing, migrations, deprecations, public commitments) get the full gate.
- Stage log in `00-product-context.md` (create if absent): a table `| stage | artifact file | initiative | date | status |` — add or update your row whenever you save an artifact. Durable learnings file as INSIGHT-NNN entries in `85-insight-log.md`, the single cross-initiative memory (claim, source, confidence, implications, status; log within 48h; disconfirmed entries get marked and linked, never deleted).
- Repeat runs for a new feature/initiative: include an initiative slug in filenames — `NN-<stage>-<slug>-<artifact>.md` — and never overwrite another initiative's files. Product-level singletons (context, positioning, strategy, insight log) update in place with a dated changelog line at the bottom.
- Adapt depth to the user profile in the context file (ask once if unknown): solo founder → lightest artifact, minimum ceremony; team PM → emphasize alignment and decision rationale; learner → briefly explain why each step exists as you go. If authoring mode is `guide-only`, structure, question, and critique so the user writes the artifact themselves; if they still ask you to draft, nudge once toward their own words, then help fully — it's their product.
- One round of questions max before drafting; then proceed on documented `[ASSUMPTION]`s rather than interrogating.

## Framework menu — pick by the decision being made

| Document | Decides | Pick it when |
|---|---|---|
| **Lean Canvas** (Ash Maurya) | "Is this even a business?" | Brand-new product/startup idea; the business model itself is unvalidated. One page: problem, segments, unique value proposition, solution, channels, revenue, costs, key metrics, unfair advantage. Note: if you're reaching for this, you're really at stages 1–3 — offer discovery-validation first. |
| **PR-FAQ / Working Backwards** (Amazon) | "Should we build this at all?" | New products or major initiatives before commitment. Future press release (customer problem → solution → quotes → how to start) + external FAQ (price, availability) + internal FAQ (market size, technical risk, economics, what must be true). |
| **One-pager** | "Are we aligned enough to start?" | Default for features in an existing product. Problem, evidence, goals + non-goals, target user, success metrics, proposed approach, open questions, risks. |
| **Full PRD** | "What exactly are we building?" | Cross-team work, high-stakes or regulated surface area, or when the one-pager's open questions are resolved and detail is needed. |
| **User stories + acceptance criteria** | "How does it break into buildable increments?" | After direction settles; the handoff into delivery. |

Escalate weight only when the decision demands it: canvas → PR-FAQ → one-pager → PRD → stories. A solo founder rarely needs more than canvas + one-pager + stories. Recommend one; the user picks.

## Workflow

1. **Confirm the decision** this document serves and pick the lightest format that serves it (menu above). Writing a 12-page PRD to decide "should we explore this?" is the classic failure.
2. **Inherit upstream content.** Pull the problem and evidence from discovery, the target user from positioning, and the success-metric candidates from strategy's North Star inputs *and this item's roadmap-row success signal* — the PRD metric should refine that signal, not replace it. Pull the still-open high-importance assumptions from the assumption map into Risks & mitigations, keeping their evidence rating. Show the user what you inherited so they can correct staleness.
3. **Draft the document from its template** — read the matching reference first and follow its structure and quality bar:
   - **One-pager / full PRD / stories + AC:** `references/prd-onepager.md` — carries the core sections (goals, non-goals, success metrics with owner + review date, assumptions register with confirm/kill, pivot criteria), the full-PRD adds (unhappy paths, permissions/abuse/migration, the written NFR sweep, tracking plan), and the story/AC rules. The traceability rule inside it is load-bearing: every must-have maps to validated pain or a tagged assumption.
   - **PR-FAQ:** `references/prfaq.md` — two-pass rule (pass 1 = labeled hypothesis with `[ASSUMPTION]` tags and `[ASPIRATIONAL]` testimonials; pass 2 = evidence-backed before any leadership read), press release in customer language, and the internal FAQ that steelmans the case against.
   - **Tracking plan** (in the PRD or as `50-requirements-<slug>-tracking-plan.md`): `| event | fires when | properties | feeds which metric |` for every success metric plus surrounding funnel steps; one naming convention (e.g., `object_action`); minimum collection, no PII in properties without privacy review, retention noted. Events fold into acceptance criteria — a story isn't done if its events don't fire.
4. **Red-team it yourself** before presenting: What's the strongest reason NOT to build this? Which section would an engineer call underspecified? Which metric could be gamed? Would legal/privacy need to see this — personal data, payments, minors, health or financial data, or a new jurisdiction means review at PRD time, not launch week? Put the answers into Risks/Open Questions rather than polishing them away.
5. **Set the review loop.** For anything technically novel, get an engineering **feasibility read before the build is committed** — a 1–2 day spike on the scariest unknown beats a confident estimate; record the verdict in Risks. Then have engineering + design read the doc before any estimate is treated as real; open questions get owners and dates. Offer artifact-critique as a formal gate for high-stakes docs.
6. **Route forward:** stories and the PRD feed delivery-planning; success metrics pre-register the measurement plan that metrics-iteration will execute.

## Artifact rules

Every artifact starts with `## TL;DR & So What` — **max 2 paragraphs, plain language**: (1) what we're building and for whom, (2) why it matters now and what happens next. (For PR-FAQs, this sits above the press release.)

## Pitfalls checklist

- [ ] Non-goals section exists and contains real exclusions someone argued for.
- [ ] Every problem claim cites discovery evidence or carries an `[ASSUMPTION]` tag with confirm/kill evidence; the doc has an assumptions register.
- [ ] Success metrics have a number, a measurement method, and a review date — not "improve engagement."
- [ ] Solution describes what/why, not implementation; engineers own how.
- [ ] Edge cases, error states, NFR sweep (every line filled or consciously "n/a"), and rollout plan present in full PRDs; one-pagers name their 2–3 material NFRs.
- [ ] Every success metric has named events in the spec, not just a "measurement method."
- [ ] PR-FAQ internal FAQ includes the strongest argument against building.
- [ ] Stories are user-valuable slices with testable Given/When/Then AC, written pre-development.
- [ ] The doc is dated and marked living; someone owns keeping it true.
