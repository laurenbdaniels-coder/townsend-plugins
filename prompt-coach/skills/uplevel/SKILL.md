---
name: uplevel
description: Rewrites a draft prompt with the right guardrails for its task type and stakes, then teaches the user why each change was made. Use whenever the user asks to uplevel, improve, strengthen, fix, review, or coach a prompt; says "make this prompt better", "how should I ask this", "what's wrong with my prompt", or shares a prompt they're about to send and wants it checked. Also use proactively when the user is drafting a request for high-stakes work — anything mentioning donors, the board, press, grants, funders, client- or beneficiary-facing material, or legal matters — even if they don't ask for prompt help, because those are the tasks where a weak prompt produces confidently wrong output.
---

# Uplevel

Take the user's draft prompt and return a stronger version with the right guardrails —
no more than the stakes justify — plus a short explanation that teaches the user to do
it themselves next time. Every uplevel is a mini-lesson; the goal is that heavy users
eventually need this skill less.

## Workflow

1. **Read the playbooks.** Read `../../knowledge/playbooks.md` (relative to this
   skill's base directory) to classify the draft prompt's type and stakes tier. If the
   stakes are ambiguous, ask one question ("who's the audience for this?") rather than
   guessing high and over-guardrailing.

2. **Read the library.** Read `../../knowledge/prompt-library.md` and pick the specific
   guardrail prompts the playbook calls for. Read
   `../../knowledge/current-guidance.md` section 3 for the prompt-construction
   practices (XML structure, document-first ordering, examples, positive framing) and
   apply the ones that fit.

3. **Rewrite the prompt.** Preserve the user's intent and voice; add only what the
   playbook justifies. A brainstorming prompt gets scope control and nothing else —
   over-guardrailing light work is this skill's main failure mode, and it's not just
   an adoption problem: over-prescription measurably degrades output quality on
   current models, and instruction adherence drops as instruction count rises.
   **Budget: 3–5 guardrails maximum, the must-not-fail instruction first, and trim
   at least as much as you add** — cut redundant phrasing, dead constraints, and
   anything the model does by default now (e.g., "think step by step"). The evidence
   basis for this whole skill: measured prompt-improvement tools raised task accuracy
   ~30% in Anthropic's testing — rewriting prompts works; bloating them doesn't.

4. **Show your work in this format:**

   **Your prompt** — the original, unchanged.

   **Upleveled prompt** — the rewrite, in a copyable block.

   **What changed and why** — each change on one line, named to its strategy
   (e.g., "Added an out (Prevent): without permission to say 'I don't know', the model
   fills gaps with plausible guesses").

   **One tip** — a single skill the user could apply themselves next time. Pick the
   highest-leverage gap in their draft, not a generic tip.

5. **Close honestly.** If the task is strict-tier, remind the user in one sentence that
   an upleveled prompt reduces errors but does not remove the need for human
   verification before the output ships.

## Boundaries

- This skill owns the *prompt*. If the user's task is creating the org's external content
  (donor letters, press releases, board updates), uplevel the prompt, then let the
  org's content and fact-check skills own the *content* — don't duplicate their job.
- Don't rewrite prompts the user didn't share for review, and don't run this skill on
  casual conversational questions — it's for prompts that do real work.
