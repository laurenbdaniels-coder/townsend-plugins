# Prompt-Type Playbooks

The uplevel skill classifies each prompt into one of these types, then applies the
guardrails listed. Strategy numbers refer to `current-guidance.md` section 3 and
`prompt-library.md`.

## How to classify

Read the user's draft prompt and pick the closest type below. If it spans two types,
apply the union of their guardrails. Then determine the stakes tier (see
`current-guidance.md` section 4) from the audience and the presence of high-stakes
markers: donor, board, press, grant, homeowner-facing, legal, funder, media, public.

## Playbooks

### Research / factual Q&A
Failure modes: stale facts, invented specifics, false premises accepted.
Apply: #2 Ground (search-don't-recall), #1 Prevent (give-an-out), #5 Premise check,
citation per claim. Strict tier adds: #6 uncertainty labels.

### External writing (donor, grant, press, appeal, board)
Failure modes: invented statistics, misattributed quotes, off-brand claims.
Apply: #2 Ground (build-on-my-facts-only), #1 Prevent (no gap-filling), #4 stakes
declaration, #3 quote-or-retract on the draft. Always strict tier.
For HFH SKC content, hand the *content* itself to the org's content/fact-check skills
if installed — this plugin owns prompting hygiene, not Habitat facts or brand voice.

### Data / numbers / analysis
Failure modes: inline arithmetic errors, confident estimates presented as computation.
Apply: compute-with-code requirement, #3 redo-the-math, #6 know/infer/guess split.

### Long-document summary or extraction
Failure modes: lost-in-the-middle misses, blended paraphrase presented as content.
Apply: document-first ordering (doc at top, question at end), #2 quotes-first,
XML tags separating instructions from input.

### Decision support / recommendations
Failure modes: sycophantic agreement with the user's lean, unexamined premises.
Apply: #5 premise check, #7 stress test (steelman + failure modes), #8 anti-folding
rules up front, #6 confidence with reasons.

### Brainstorming / creative
Failure modes: over-guardrailing kills usefulness — the main risk here is friction.
Apply: #9 scope control only. Do not add the verification battery. Light tier.

### People / HR-sensitive
Failure modes: confidentiality drift, scope creep into individual-level data.
Apply: #9 hard boundaries, #1 give-an-out. If the org has dedicated People & Culture
skills installed, defer the substance to them.

### Recurring / routine tasks
Apply: #4 routinize — build a reusable template with grounding, an uncertainty flag,
and a closing verification checklist baked in.

## Output construction rules (all types)

- Restructure with XML tags when the prompt mixes instructions, context, and input.
- Add the "give the reason" line (who it's for, what it enables) if missing — it's the
  cheapest quality upgrade available.
- Make action and scope explicit: "do" vs. "suggest", "every section, not just the first."
- Add 3–5 examples when format/tone control matters and examples exist (they steer
  format and voice, not accuracy — start zero-shot otherwise).
- Use positive framing: what to do, not what to avoid.
- **Instruction budget:** pick the 3–5 guardrails the stakes require, put the
  must-not-fail instruction first, and trim as much as you add — over-prescription
  measurably degrades output quality on current models, and adherence drops as
  instruction count rises. Friction also kills adoption.
- Don't add "think step by step" — current models reason adaptively; reserve
  step-by-step for math verification (or require code).
