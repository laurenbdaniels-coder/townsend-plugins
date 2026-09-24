# Prompt Coach — Current Guidance (Knowledge Base)

Version: 0.4
Last reviewed: 2026-08-12
Owner: Lauren Townsend

This is the living knowledge base the Prompt Coach plugin runs on. The refresh skill
maintains it; the uplevel, check-answer, and coach skills read from it. Team-facing
prose lives in your team handout, if you keep one; this file is
the condensed operational version.

Sibling files in this knowledge folder:
- `prompt-library.md` — the full copy-paste prompt library (nine strategies)
- `playbooks.md` — prompt-type playbooks and stakes tiers
- `sources.md` — pinned source allowlist for refresh
- `changelog.md` — version history

## Topic areas (refresh searches each of these)

1. Model weak spots / failure modes
2. Detecting confident wrong answers
3. Guardrail strategies and prompt patterns
4. Anti-sycophancy
5. Skill & plugin authoring practice

---

## 1. Model weak spots

- Fresh/changing facts (knowledge cutoff) — require search, not recall
- Citations and sources — most-faked artifact class; never trust unclicked
- Inline math/counting — require computation (code), not estimation
- Niche/local/internal specifics — plausible gap-filling risk
- Long documents — "lost in the middle" positional bias
- False premises in user questions — accepted and built upon by default
- Sycophancy — folds under pushback without new evidence
- Uncalibrated confidence — tone carries no information about accuracy
- Inconsistency across re-asks — instability signals ungrounded generation
- Org-internal data — knows nothing not provided or connected

## 2. Detection: red flags

Hyper-specific detail without a source; answer matches user's evident preference;
polished citations; instant reversal under pushback; zero hedging where experts hedge;
different answer on blind re-ask; math stated without work; present-day facts from
memory; fluent filler.

Sixty-second habits: blind re-ask in fresh chat; click one citation; ask "what would
make this wrong?"; independently spot-check the load-bearing fact; tier verification by
stakes (donor/board/press/homeowner-facing = human-verified source per claim).

Added v0.4: **length is not evidence** — longer, more detailed answers feel more right
without being more right (Nature Machine Intelligence); and **you won't feel sycophancy
happening** — novices reliably fail to detect it, so run the fold test on important
answers regardless of how the conversation feels.

## 3. The nine guardrail strategies

| # | Strategy | Core move |
|---|---|---|
| 1 | Prevent | Give explicit permission to say "I don't know" (Anthropic's #1 fix) |
| 2 | Ground | Provided-docs-only; quotes-first for long docs; citation per claim |
| 3 | Check | Claim-by-claim audit; quote-or-retract; redo math with code |
| 4 | Routinize | Standard closers; "verify before use" lists; stakes declarations |
| 5 | Premise protection | Check the question's assumptions before answering it |
| 6 | Surface uncertainty | Forced labels: CONFIDENT / LIKELY / UNCERTAIN |
| 7 | Stress test | Argue against own answer; skeptical-expert review; steelman |
| 8 | Anti-folding | Accuracy-over-agreement rule; evidence-only revisions; fold test |
| 9 | Scope control | Do-only-this; hard boundaries; define done before starting |

Full copy-paste prompts for each strategy: `prompt-library.md`.

### Prompt-construction practices (added v0.2, Tier 1: Anthropic prompting best practices)

- **Document-first ordering:** for long inputs (20k+ tokens), place documents at the
  top of the prompt and the question/instructions at the end — up to ~30% quality
  improvement on multi-document tasks. Pairs with quotes-first grounding.
- **XML-tag structure:** in complex prompts, separate `<instructions>`, `<context>`,
  and `<input>` so Claude never confuses your directions with the material.
- **Examples steer best:** include 3–5 relevant, diverse examples of the desired
  output (wrapped in `<example>` tags) to control format and tone.
- **Positive framing:** tell Claude what to do rather than what to avoid
  ("write in flowing prose" beats "don't use bullets").

### Task-setup practices (added v0.4, Tier 1: Anthropic model-specific guidance)

- **Give the reason:** one sentence of who the output is for and what it enables beats
  a paragraph of instructions. Template: "I'm working on [larger task] for [audience].
  They need [what the output enables]. With that in mind: [request]."
- **Whole task first:** hand Claude the complete hard job and ask it to scope the work
  and ask clarifying questions before starting — don't pre-chop everything into
  small pieces.
- **"Do," not "suggest":** current models follow instructions literally. "Can you
  suggest changes" gets suggestions. State action and scope explicitly: "apply this to
  every section, not just the first."
- **Colleague golden rule:** show your prompt to a colleague with minimal context —
  if they'd be confused, Claude will be too.
- **Lessons file for recurring work:** for monthly/weekly tasks, have Claude keep a
  running lessons file (one lesson per line) and read it at the start of each run.
- **Evidence-audited progress:** for long tasks, add "Before reporting progress, audit
  each claim against actual work from this session. Only report work you can point to
  evidence for; if something is not yet verified, say so." (Anthropic: nearly
  eliminated fabricated status reports.)
- **No magic words:** results are brittle to small wording changes, and no technique
  helps consistently across tasks. Test recurring templates on 2–3 real examples
  before trusting them month-to-month.
- **Instruction budget:** adherence measurably degrades as instruction count rises,
  and over-prescription degrades output quality on current models. Pick the 3–5
  guardrails the stakes require, put the must-not-fail instruction first, and trim as
  much as you add.

### What doesn't work (added v0.4 — teach against these)

- **"Think step by step" as an accuracy tip** — retired. Current models reason
  adaptively by default; prefer general instructions ("think thoroughly about the
  tradeoffs"). Keep step-by-step only as a *verification* move for math, or better,
  require code.
- **Personas for accuracy** — "you are an expert grant writer" shapes tone and style;
  it does not make facts more correct (162-persona study: no accuracy gain).
- **Politeness, tipping, threats** — no reliable effect; unpredictable noise.
- **Unanchored self-correction** — "critique and improve your answer" without an
  external anchor (documents, math, code) often makes answers worse. Self-correction
  works when grounded: quote-or-retract, redo-with-code, check-against-source.

### Calibration cautions (added v0.4)

- **Labels are triage, not truth:** [CONFIDENT] tells you what to check *last*, not
  what to skip. A CONFIDENT label never downgrades the verification tier — verbalized
  confidence is systematically overconfident.
- **Examples control format and voice, not accuracy.** Start zero-shot on current
  models; add 3–5 examples when format/tone control matters.
- **Sycophancy compounds over long conversations** (emerging finding — treat as
  caution): for important decisions, restate the accuracy-over-agreement rule late in
  a long chat, or move the final check to a fresh chat.

## 4. Stakes tiers

- **Light** (internal brainstorm/drafts): scope control only; skip the battery.
- **Standard** (team-facing work): give-an-out + grounding + standard closer.
- **Strict** (donor, board, press, grant, homeowner-facing, legal): full battery —
  grounding, citation per claim, premise check, uncertainty labels, human verification
  of every factual claim before shipping. Never a "verified" stamp; always a
  "verify before use" list.

High-stakes markers that trigger strict tier: donor, board, press, grant,
homeowner-facing, legal, funder, media, public.

## 5. Skill & plugin authoring practice (for maintaining Prompt Coach itself)

- SKILL.md under ~500 lines; push content into shared knowledge/ (progressive disclosure)
- Description = what it does + when to trigger, third person, slightly "pushy" to
  counter under-triggering; all "when to use" info in the description, not the body
- Explain why, not just what — avoid rigid ALL-CAPS musts where reasoning works
- Bundle scripts for deterministic work; markdown for judgment work
- Test with realistic prompts + baseline comparison (skill-creator eval loop);
  optimize the description against should/shouldn't-trigger evals
- Refresh updates knowledge/ files only; never any skill's workflow/security logic

## Sources backing this guidance

Anthropic reduce-hallucinations guide and consolidated prompting best practices with
per-model pages for Fable 5 / Sonnet 5 / Opus 5 (platform.claude.com); Anthropic
prompt-eng-interactive-tutorial and courses repos (github.com/anthropics — courses repo
is Claude 3-era, use as history not doctrine); Anthropic AI Fluency curriculum
(anthropic.com/learn); Anthropic prompt improver results (anthropic.com/news);
Anthropic engineering: effective context engineering; Farquhar et al., semantic
entropy, Nature 2024; Steyvers et al., calibration gap, Nature Machine Intelligence
2025; Vaccaro et al., human-AI combination meta-analysis, Nature Human Behaviour 2024;
The Prompt Report (arXiv:2406.06608); Prompting Science Reports 1–3 (arXiv:2503.04818,
2506.07142, 2508.00614); IFScale instruction-overload (arXiv:2507.11538); LLMs Cannot
Self-Correct Reasoning Yet (arXiv:2310.01798); personas study (arXiv:2311.10054); ROPE
requirement-oriented prompt engineering (arXiv:2409.08775, ACM TOCHI); spacing &
retrieval practice review (Nature Reviews Psychology 2022); OpenAI sycophancy
postmortems (openai.com); Malmqvist, sycophancy causes & mitigations
(arXiv:2411.15287); lost-in-the-middle literature; legal citation reliability
benchmarks (LegalCiteBench, AusLaw).
