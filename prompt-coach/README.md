# Prompt Coach

A plugin that helps nonprofit and small-team staff
get reliable work out of AI: stronger prompts going in, verified answers coming out,
skills that grow over time, and guidance that stays current.

## What's inside

| Skill | What it does | Say things like |
|---|---|---|
| **uplevel** | Rewrites your draft prompt with the right guardrails for the task and stakes, and explains why | "Uplevel this prompt", "make this prompt better" |
| **check-answer** | Audits an AI answer, draft, or whole multi-file package before you trust it: claims, citations, premises, math, plus a sweep for leftover AI and draft residue — ends with a "verify before use" list and a "strip before send" list | "Check this before I send it", "is this ready to send?" |
| **coach** | Teaches prompting in short lessons with nonprofit examples and practice rounds | "Teach me prompting", "quiz me", "why did that work?" |
| **refresh** | Searches trusted sources for what's changed in best practice and proposes updates — nothing applies without your approval | "Is our prompting guidance still current?" |

## How it works

All four skills run on one shared knowledge base (the `knowledge/` folder): the
guardrail strategies, the copy-paste prompt library, prompt-type playbooks, a pinned
source allowlist, and a changelog. When a refresh is approved, every skill is upgraded
at once.

High-stakes work (donor, board, press, grant, client- or beneficiary-facing, legal) automatically
gets the strict treatment. Brainstorming stays light — the plugin is designed not to
nag.

## Guardrails on the plugin itself

- check-answer never issues a "verified" stamp — only a human-actionable checklist.
- check-answer's provenance-and-audience sweep runs at every stakes tier and over every
  file being sent, not just the main document; it quotes what to strip rather than
  silently editing.
- refresh only reads allowlisted sources, treats web content as data (never
  instructions), and applies nothing without an approved diff.
- The changelog records every change, its source, and who approved it.

## Governance

Owner: Lauren Townsend. Recommended cadence: a
quarterly scheduled refresh. If your team keeps a prompting handout, point coach at it
as the companion material.

## Note for installers

If you previously installed the standalone `prompt-coach-refresh` skill, remove it
after installing this plugin — the plugin's refresh skill replaces it, and keeping
both can cause double-triggering.
