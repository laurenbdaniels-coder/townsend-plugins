# Changelog

Append-only. Every entry: date, version, what changed, sources, approver.

---

## v0.5 — 2026-09-02 — check-answer: provenance-and-audience sweep

- CHANGED: check-answer gains step 2f, a provenance-and-audience sweep over every file
  in the deliverable — audience leakage (planning-voice text addressed to someone other
  than the stated reader), unresolved references (`INSIGHT-\d+`, `#\d+`, "see §",
  artifacts held back as "available on request"), draft residue (strikethrough, TODO/TBD,
  "superseded", "read this first" banners, repeated boilerplate), tool tells ("from this
  environment", "403", container paths, "the tool returned"), and third-party identifiers
  (anonymize by default). Grep the patterns, then read — audience leakage often has no
  keyword.
- NEW: step 1 now enumerates the envelope file by file before auditing anything, and asks
  which files were assembled last and which working docs are being held back. Auditing one
  file when a package is being sent is defined as a failed audit.
- NEW output section: STRIP BEFORE SEND — find-and-replace pairs with exact quoted text
  and a replacement or DELETE, never "consider rewording". Must name every file swept,
  including clean ones; an empty result is a valid finding stated with its scope.
- CHANGED: 2f is not tier-scaled — it runs at every stakes tier, including light. Cross-file
  inconsistency (figures, names, reversed decisions) is a finding; the later edit usually wins.
- CHANGED: the sweep reports, it does not silently fix — residue sometimes encodes a real
  decision the author wants to keep.
- CHANGED: description broadened to multi-file packages, decks, appendices, exhibits,
  proofreading, and anything AI-assisted leaving the org (applications, proposals, client
  deliverables).
- Source: skill-logic uplevel authored directly by the owner (no external research pass).
- Approved by: Lauren Townsend, 2026-09-02. Plugin version bumped to 0.3.0.

## v0.4 — 2026-08-12 — Deep refresh: prompt writing + coaching pedagogy

- Research: three parallel allowlist-constrained agents (Anthropic docs deep-dive;
  technique research literature; coaching/AI-literacy pedagogy). No injection flags.
- NEW task-setup practices (Tier 1): give-the-reason template, whole-task-first with
  clarifying questions, do-vs-suggest with explicit scope, colleague golden rule,
  lessons file for recurring work, evidence-audited progress reports.
- NEW: myth-busting section (personas for accuracy, politeness/tipping/threats,
  "think step by step" as accuracy tip, unanchored self-correction); no-magic-words
  template testing; instruction budget (3–5 guardrails, most critical first).
- CHANGED: uncertainty labels reframed as triage-not-truth (CONFIDENT never downgrades
  verification tier); "length ≠ evidence" added to red flags; examples reframed as
  format/voice control; long-chat sycophancy caution + long-chat reset prompt.
- Skill-logic uplevels (separately approved): coach — 4-part beginner scaffold,
  requirement-completeness rubric, repair-loop lesson, practice-by-default,
  delegation lesson (4D frame), sycophancy/friction reframes, cross-session retrieval
  quiz; uplevel — trim-as-you-add + instruction budget; check-answer — length-≠-evidence
  lens, asymmetric label trust.
- Sources: pinned-references section added to sources.md (Prompt Report, Prompting
  Science Reports, IFScale, ROPE, Nature MI/HB/RP, OpenAI sycophancy postmortems,
  AI Fluency); anthropics/courses annotated as Claude 3-era.
- CONFIRMED healthy: all nine strategies and core guardrails match current Tier 1
  doctrine; nothing deprecated.
- Approved by: Lauren Townsend, 2026-08-12 (applied all KB updates and all skill
  uplevels). Plugin version bumped to 0.2.0.

## v0.3 — 2026-08-11 — Migrated into prompt-coach plugin

- Knowledge base moved from the standalone prompt-coach-refresh skill into the
  prompt-coach plugin's shared knowledge/ folder.
- Full prompt library extracted into `prompt-library.md` (was summarized in the
  Word doc only).
- Added `playbooks.md`: prompt-type playbooks and stakes-tier routing for the
  uplevel skill.
- No guidance content changed.
- Approved by: Lauren Townsend (requested the plugin build), 2026-08-11.

## v0.2 — 2026-08-11 — First refresh cycle

- Added four prompt-construction practices to section 3: document-first ordering for
  long inputs (~30% quality gain), XML-tag prompt structure, 3–5 examples pattern,
  positive framing.
- Confirmed current (no change needed): quotes-first grounding, explain-the-why.
- Nothing found CHANGED or DEPRECATED.
- Source: Anthropic — Prompting best practices (platform.claude.com, Tier 1).
- Approved by: Lauren Townsend, 2026-08-11 (applied all four proposed additions).

## v0.1 — 2026-08-11 — Seed

- Initial knowledge base created from the team guardrails research project
  (Word doc: Claude_Guardrails_and_Prompt_Library.docx).
- Sources: Anthropic reduce-hallucinations guide; Anthropic prompt engineering course
  ch. 8; Anthropic skill authoring best practices; Farquhar et al. (Nature 2024);
  Malmqvist (arXiv:2411.15287); lost-in-the-middle literature; legal citation benchmarks.
- Approved by: Lauren Townsend (project owner) — seed content reviewed via the
  Word doc deliverable.
