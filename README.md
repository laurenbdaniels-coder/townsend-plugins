# Townsend Plugins

**TL;DR & So What:** A Claude Code / Cowork plugin marketplace with four plugins from Townsend AI Studio: **product-flow** (a ten-skill, stage-by-stage product management workflow — from "is this problem real?" to "did the launch work?" — with fill-in templates, evidence rules, and a built-in critique gate), **pm-growth-coach** (a self-development coach that baselines your PM competencies and builds a deliberate-practice growth plan grounded in your real work artifacts), **prompt-coach** (upleveled prompts with the right guardrails, plus a verification battery that audits an AI draft before it ships), and **custody-check** (the eleven custody questions from the workshop "It Said It Was Fine", run read-only on an AI-built app, with a verdict: ship it, patch it, or shelve it).

So what: install once, and Claude becomes your product process, your PM development partner, and the check that keeps AI-drafted work from shipping unverified — in Claude Code, Cowork, or anywhere Claude plugins run.

## Install (Claude Code)

From GitHub (https://github.com/laurenbdaniels-coder/townsend-plugins):

```
/plugin marketplace add laurenbdaniels-coder/townsend-plugins
/plugin install product-flow@townsend-plugins
/plugin install pm-growth-coach@townsend-plugins
/plugin install prompt-coach@townsend-plugins
/plugin install custody-check@townsend-plugins
```

Or from a local clone of this folder:

```
/plugin marketplace add /path/to/townsend-plugins
/plugin install product-flow@townsend-plugins
```

For quick local testing without installing: `claude --plugin-dir /path/to/townsend-plugins/product-flow`

## What's inside

| Plugin | Version | What it does |
|---|---|---|
| product-flow | 1.2.0 | Full product lifecycle: workflow guide, discovery, positioning, strategy (with the Insight → Data → Implication why-case), prioritization, PRD, delivery + validation, launch, metrics, and an artifact critique gate. Shared `product-workspace/` so every stage builds on the last. |
| pm-growth-coach | 0.1.0 | Develops the PM, not the product: five-dimension competency baseline, leverage-based focus, weekly practice reps, evidence-based re-scoring. Reads the product-flow workspace as evidence when present. |
| prompt-coach | 0.3.0 | Guardrails for AI work: `uplevel` rewrites a draft prompt for its task type and stakes tier, `check-answer` runs a verification battery over an answer or a whole multi-file package (claim audit, citation click-list, premise check, recomputed math, fold test, provenance-and-audience sweep) and returns "verify before use" plus "strip before send" lists, `coach` teaches the nine strategies, and `refresh` keeps the shared `knowledge/` base current against a pinned source allowlist. Built for Habitat for Humanity SKC. |
| custody-check | 0.1.0 | The workshop giveaway: eleven custody questions for AI-built apps, answered read-only by a python scanner plus your own answers, rendered as a verdict with the tier of your next change, the stop-line, a door (ship, patch, shelve), and a sixty-second test for every "don't know". Also runs in Codex. See `custody-check/README.md`. |

## Updating

Bump the plugin's `version` in its `.claude-plugin/plugin.json` and this file's table, commit, push — installed copies update from the marketplace.
