# Townsend Plugins

**TL;DR & So What:** A Claude Code / Cowork plugin marketplace with six plugins from Townsend AI Studio (plus the decision-census pointer): **product-flow** (a ten-skill, stage-by-stage product management workflow — from "is this problem real?" to "did the launch work?" — with fill-in templates, evidence rules, and a built-in critique gate), **pm-growth-coach** (a self-development coach that baselines your PM competencies and builds a deliberate-practice growth plan grounded in your real work artifacts), **prompt-coach** (upleveled prompts with the right guardrails, plus a verification battery that audits an AI draft before it ships), **custody-check** (the eleven custody questions from the workshop "It Said It Was Fine", run read-only on an AI-built app, with a verdict: ship it, patch it, or shelve it), **build-decisions** (a short analysis of how an AI-built app is built and where it decides who can see a record, what something costs, whether someone has paid, and how money rounds, and which of those decisions it makes in more than one place; formerly decision-census), and **spell-it-out** (when Claude stops to ask you something technical, it first spells out what each answer does, whether you can undo it, and its pick).

So what: install once, and Claude becomes your product process, your PM development partner, and the check that keeps AI-drafted work from shipping unverified — in Claude Code, Cowork, or anywhere Claude plugins run.

## Install (Claude Code)

From GitHub (https://github.com/laurenbdaniels-coder/townsend-plugins):

```
/plugin marketplace add laurenbdaniels-coder/townsend-plugins
/plugin install product-flow@townsend-plugins
/plugin install pm-growth-coach@townsend-plugins
/plugin install prompt-coach@townsend-plugins
/plugin install custody-check@townsend-plugins
/plugin install build-decisions@townsend-plugins
/plugin install spell-it-out@townsend-plugins
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
| prompt-coach | 0.3.1 | Guardrails for AI work: `uplevel` rewrites a draft prompt for its task type and stakes tier, `check-answer` runs a verification battery over an answer or a whole multi-file package (claim audit, citation click-list, premise check, recomputed math, fold test, provenance-and-audience sweep) and returns "verify before use" plus "strip before send" lists, `coach` teaches the nine strategies, and `refresh` keeps the shared `knowledge/` base current against a pinned source allowlist. |
| custody-check | 0.5.1 | The workshop giveaway: eleven custody questions for AI-built apps, answered read-only by a python scanner, a read of your code, and your own answers, rendered as a verdict with the tier of your next change, the stop-line, a door (ship, patch, shelve), and a sixty-second test for every "don't know". Free, so it finds and checks; it never gives the fix. Also runs in Codex. See `custody-check/README.md`. |
| build-decisions | 0.5.0 | The companion to custody-check: says in plain words how an AI-built app is built (browser to database, its own server code, a second app sharing the data) and where it saves whether someone has paid, finds where it decides who can see a record, what something costs, whether someone has paid, and how money rounds, and gives a short plain-English analysis of each decision made in more than one place, with a one-minute check by hand. Read-only: a python helper lists the starting places and the agent searches the code from there. Never says the app is clean. See `build-decisions/README.md`. |
| decision-census | 0.3.3 | The old name of build-decisions, kept as a pointer: it prints the three commands to switch and runs nothing. |
| spell-it-out | 0.1.0 | Plain-English stops: before a technical yes/no, choice or approval, Claude writes a short brief (the ask, where we are, if yes / if no, undo, its pick, the safe answer if you're not sure, a TL;DR). Questions about taste, wording, people or dates stay plain. Optional `CLAUDE.md` lines make it a standing rule. See `spell-it-out/README.md`. |

## Free plugins

A free plugin that checks an app diagnoses and never prescribes the fix. New free plugins that check an app follow [the free-plugin report standard](free-plugin-standard/STANDARD.md), and their evals carry its shared graders. build-decisions is the reference implementation.

## Updating

Bump the plugin's `version` in the three places that have to agree: its own `.claude-plugin/plugin.json`, its entry in the marketplace manifest `.claude-plugin/marketplace.json`, and this file's table. custody-check has a fourth: `__version__` in `custody-check/skills/custody-check/scripts/custody_scan.py`, which prints in every verdict footer and which CI checks against `plugin.json`. build-decisions has the same fourth place: `__version__` in `build-decisions/skills/build-decisions/scripts/census_scan.py`. The `decision-census` pointer has no helper: its `plugin.json` and marketplace entry agree. Then commit and push — installed copies update from the marketplace.

Maintainers: before your first push from a clone, install the pre-push check into the clone's shared hooks folder: `cp .githooks/pre-push "$(git rev-parse --git-common-dir)/hooks/pre-push"`, and copy it again whenever the hook changes. Don't use `core.hooksPath .githooks`: that path is relative, so any checkout of a branch without the hook pushes with no check at all, and git says nothing. It refuses a push if a term from a private list kept outside this repo appears in a pushed ref name or in anything the push sends that the remote does not already have: file contents, file and symlink names, commit authors and messages, tag messages. It catches accidents, not deliberate hiding (a term split across lines or inside a zip is missed), and it covers pushes from this repo only, not submodules. It fails closed: with no list it refuses, unless you set `TOWNSEND_ALLOW_NO_TERMS=1`. Tests: `python3 -m unittest discover -s .githooks`.

## License

MIT. See [LICENSE](LICENSE).
