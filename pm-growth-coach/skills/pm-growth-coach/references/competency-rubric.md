# PM Competency Rubric — Self-Assessment Edition

Five dimensions, scored 1–10 against behavioral anchors — the same axes used by the companion coach-side kit, so coached and self-directed development measure the same things. Score to the nearest anchor band: a delta smaller than one band is recorded as "trending toward [anchor]" with the specific new behavior cited, never as a number bump — the 6-vs-7 distinction is unfalsifiable and not worth arguing with yourself about. Scoring rules: every score cites evidence (an artifact, a concrete recent situation, a pattern across work); no averaging across dimensions into one "PM score" (the shape matters more than the mean); a score without evidence is written as "unscored" — the first rep then exists to generate evidence.

---

## How to read the anchors

Anchors describe *observable behavior* at roughly 2 (developing), 5 (solid), and 8 (advanced). Score between anchors freely. Evidence to look for is listed per dimension — if a `product-workspace/` exists, these map to real files.

## 1. Structured discovery

*Finding out what's true about customers and problems before committing.*

- **~2:** Talks to customers rarely or asks hypothetical/leading questions; treats compliments as validation; conclusions don't cite counts or sources.
- **~5:** Runs past-behavior interviews with a guide; synthesizes with sources and counts; distinguishes evidence from assumption most of the time.
- **~8:** Pre-registers what would change their mind before research; actively hunts disconfirming evidence; kills their own hypotheses in writing; discovery visibly changes decisions.
- **Workspace evidence:** interview guides (hypotheticals present?), synthesis readouts (sources? counts? "looked for and didn't find" section?), assumption maps, whether roadmap/PRD decisions cite discovery.

## 2. Systems thinking

*Seeing how the pieces connect — metrics to strategy, edge cases to architecture, this quarter to next year.*

- **~2:** Treats features in isolation; specs cover the happy path; surprised by second-order effects (support load, metric conflicts, migration pain).
- **~5:** Specs cover failure paths and NFRs; sees the main dependencies; connects features to the metric they serve.
- **~8:** Reasons in loops and tradeoffs unprompted — cannibalization, incentive effects, where a local win harms the system; designs guardrails before being asked; models how today's choice constrains future ones.
- **Workspace evidence:** PRDs (non-goals? edge/error cases? NFR sweep? tracking plan?), risk registers (second-order risks or only obvious ones?), metric trees, rollback plans.

## 3. Strategic narrative

*Making the case — clearly, honestly, at the right altitude for the audience.*

- **~2:** Documents are feature lists or walls of text; the "why" is implied; jargon-heavy; the ask is unclear.
- **~5:** Docs lead with the argument; a skimming reader catches it; positioning and strategy connect; metrics carry context.
- **~8:** A one-page narrative a skeptical executive repeats back accurately; explicit tradeoffs and NOTs; the strongest case *against* is in the doc; survives the retell test jargon-free.
- **Workspace evidence:** strategy one-pagers (real NOTs?), positioning docs (would a competitor's page read differently?), PR-FAQs (steelmanned case against?), TL;DRs (would a non-PM understand?).

## 4. Execution judgment

*Shipping the right thing predictably — sequencing, scope, and honest status.*

- **~2:** Plans are optimistic ticket lists; riskiest work lands last; scope grows silently; status updates hide bad news until it's a crisis.
- **~5:** Sprints/cycles have one goal; riskiest slice first; scope trades are explicit; status is honest with a path to green.
- **~8:** Right-sizes ceremony to the situation; pre-commits success criteria and rollback triggers; cuts scope early and tells everyone why; estimates calibrate against actuals over time.
- **Workspace evidence:** delivery plans (goal or grab-bag? riskiest-first?), status updates (bad news early? paths to green with owners/dates?), landing reviews (estimate-vs-actual recorded?), decision logs.

## 5. Stakeholder management

*Getting decisions made and keeping trust — up, across, and with customers.*

- **~2:** Surprises stakeholders; relitigates decided questions; avoids conflict until it explodes or concedes to whoever is loudest.
- **~5:** Maps who decides/consults/informed; communicates on a cadence; disagreements surfaced with options and a recommendation.
- **~8:** Builds alignment before the meeting; makes "no" easy to say and hear by pre-agreeing criteria; converts opponents by representing their view better than they do; decision logs kill re-litigation.
- **Workspace evidence:** comms plans, decision logs (options + rationale recorded?), roadmap rationale ("not chosen and why" present?), go/no-go docs (criteria pre-aligned or written the night before?).

---

## Transition halo warning

Entering PM from an adjacent role inflates the nearest dimension: ex-marketers over-score strategic narrative, ex-engineers over-score systems thinking, ex-support over-score structured discovery ("I know what customers want"). The tell: high self-score, thin artifact evidence. Score the *PM behaviors*, not the adjacent-role fluency. The halo is a prompt to demand evidence, not a penalty — if the artifacts support the high score, keep it and say so.

## Scoring output format

| Dimension | Score | Evidence (artifact/situation, cited) | Confidence |
|---|---|---|---|
| Structured discovery | n/10 or unscored | … | High/Med/Low |

Plus two lines: **strongest dimension and the evidence for it** (keep doing this) and **the shape of the profile** (e.g., "strong narrative, thin discovery — persuasive about unvalidated things" — name the risk the shape creates).
