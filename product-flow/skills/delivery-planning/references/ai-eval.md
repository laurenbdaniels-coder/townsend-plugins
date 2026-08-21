# AI Feature Eval Plan — Template

Required for any generative/LLM-powered feature. Deterministic pass/fail testing does not cover non-deterministic outputs: the same input can produce different answers, and "works on my prompt" is not a quality bar. The PM owns defining what "good" means and where the ship line sits; engineering owns the harness. Write this before the feature is built; it gates every subsequent prompt/model change. *Solo founder: a 20-case golden set and a weekly manual scoring pass is a legitimate v1 of everything below.*

---

## TL;DR & So What

*Max 2 paragraphs, plain language: (1) what quality means for this feature and where the ship bar sits, (2) what happens if evals fail — and when they run next.*

## 1. Quality definition

*What does "good" mean here? Score on the dimensions that matter — typically: correctness (factually right), grounding (claims traceable to provided sources, no invention), tone/voice fit, safety (no harmful or off-policy output), latency. State acceptable trade-offs explicitly, e.g., "a refusal is better than a guess."*

- Dimensions and definitions: TK
- Acceptable trade-offs: TK

## 2. Failure modes and severity

| Failure mode | Example | Severity (blocker / major / minor) | Why |
|---|---|---|---|
| Hallucination (invented facts, citations, entities) | TK | TK | TK |
| Grounding break (claim not traceable to source) | TK | TK | TK |
| Harmful / off-policy output | TK | TK | TK |
| Quality drift over time (model, data, or usage shift) | TK | TK | TK |

## 3. Golden set

*The fixed test suite: 20–100+ representative inputs including edge cases, adversarial inputs, and the failure modes above — each paired with a reference output or rubric anchors (what a 1 vs. a 5 looks like). Define how the set grows: real production failures and surprising wins get added on a stated cadence, so the set tracks reality instead of launch-day imagination.*

- Size and composition: TK
- Owner/curator: TK
- Growth rule (from production): TK

## 4. Scoring method

*How outputs get judged: rubric scoring per dimension; LLM-as-judge for scale (spot-checked by a human on a stated sample rate); human review for blocker-severity dimensions. State the pass bar per dimension and overall.*

- Method + human spot-check rate: TK
- Ship bar: TK (pre-committed — per `standards/decision-frameworks.md`, post-hoc thresholds always pass)

## 5. Run cadence and drift monitoring

*Evals re-run before every prompt/model/retrieval change and on a standing schedule after launch. Define the production drift signals (score trend on sampled outputs, user-report rate, refusal rate) and who watches them.*

## Quality bar

- [ ] Quality dimensions and trade-offs written before build
- [ ] Failure modes enumerated with severity; blockers gate the launch
- [ ] Golden set exists, has an owner, and has a growth rule
- [ ] Ship bar pre-committed, not set after seeing results
- [ ] Re-run trigger (any prompt/model change) and drift monitoring named
- [ ] Eval results feed the go/no-go AI-quality row (launch-gtm)
