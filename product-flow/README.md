# product-flow

**TL;DR & So What:** product-flow is a Claude plugin with ten skills that walk you through building a product the way experienced product managers do — one stage at a time, from "is this problem real?" to "did the launch actually work?" Each stage offers a short menu of proven frameworks with plain guidance on which to pick, saves its output into a shared `product-workspace/` folder, and reads what earlier stages produced, so your PRD knows what your discovery found and your launch plan knows what your PRD promised.

So what: instead of asking Claude for isolated documents and stitching them together yourself, you get a connected, guided process with a built-in critic — and every artifact leads with a two-paragraph plain-language summary, so you (and anyone you share it with) always know what it says and why it matters. Start with `product-workflow-guide` if you're not sure where you are; start with any stage skill if you are.

## Install

For local testing (Claude Code):

```
claude --plugin-dir /path/to/product-flow
```

To install permanently, the plugin needs to live in a marketplace. Simplest local setup: create a folder (e.g. `my-marketplace/`) containing `product-flow/` and a `.claude-plugin/marketplace.json`:

```json
{
  "name": "my-marketplace",
  "owner": { "name": "Your Name" },
  "plugins": [{ "name": "product-flow", "source": "./product-flow", "description": "Stage-by-stage product management workflow" }]
}
```

Then:

```
/plugin marketplace add /path/to/my-marketplace
/plugin install product-flow@my-marketplace
```

(Or push the marketplace folder to GitHub and use `/plugin marketplace add owner/repo`.) In Cowork, install through any marketplace that includes this plugin.

## The stage map

| # | Stage | Skill | You leave with |
|---|-------|-------|----------------|
| 0 | Orient | `product-workflow-guide` | Project context file + a recommendation of which stage to do next |
| 1 | Discovery & validation | `discovery-validation` | Interview guides, assumption map, validated problem statement |
| 2 | Market & positioning | `market-positioning` | Competitive landscape, market sizing, positioning doc |
| 3 | Strategy & vision | `strategy-vision` | Vision statement + strategy one-pager + North Star metric |
| 4 | Prioritization & roadmap | `roadmap-prioritization` | Scored backlog + Now/Next/Later roadmap |
| 5 | Requirements | `requirements-prd` | Lean Canvas, PR-FAQ, one-pager, or full PRD + user stories |
| 6 | Delivery planning | `delivery-planning` | Sprint/cycle plan, risk register, stakeholder comms cadence |
| 7 | Launch & GTM | `launch-gtm` | Launch tier, GTM checklist, messaging house, launch brief |
| 8 | Measure & iterate | `metrics-iteration` | Metrics framework, experiment briefs, landing review |
| — | Quality gate (any time) | `artifact-critique` | Red-team review, pre-mortem, or readiness score of any artifact |

## The workspace convention

All skills share one folder in your working directory:

```
product-workspace/
├── 00-product-context.md      # who/what/stage — every skill reads this first
├── 10-discovery-*.md
├── 20-positioning-*.md
├── 30-strategy-*.md
├── 40-roadmap-*.md
├── 50-requirements-*.md
├── 60-delivery-*.md
├── 70-launch-*.md
├── 80-metrics-*.md
├── 85-insight-log.md          # INSIGHT-NNN entries — the single cross-initiative memory
└── 90-critique-*.md
```

Every artifact begins with a **TL;DR & So What** section — at most two paragraphs, in simple terms. That's a hard rule across the whole suite.

When you loop back through any stage for a second feature or initiative (typically stages 4–8), files carry an initiative slug (e.g. `50-requirements-payments-prd.md`) so earlier work is never overwritten; product-level docs (context, positioning, strategy) update in place with a dated changelog line.

You can run any skill standalone (they degrade gracefully with no workspace), but the suite is designed so each stage compounds on the last.

## Standards & templates (v1.1+)

Two suite-wide standards bind every skill: `standards/evidence-rules.md` (every claim gets a source, an `[ASSUMPTION]` tag, or a TK placeholder — the plugin is structurally incapable of inventing quotes or numbers) and `standards/decision-frameworks.md` (one-way/two-way door checks, pre-committed thresholds, bets with review dates). Key artifacts ship as fill-in templates with authoring guidance and quality-bar checklists in each skill's `references/` folder: interview guide, synthesis readout, wedge scorer + viability check, one-pager/PRD, PR-FAQ, validation plan + UAT, AI-feature eval plan, beta exit criteria, go/no-go, and goal status. Strategy artifacts carry a **why-case** — 2–4 Insight → Data → Implication triplets that answer why this product, why us vs. the alternatives, and why now. `evals/evals.json` carries post-install test prompts.

Design note (v1.2+ candidate): pre-launch validation currently lives in delivery-planning (validation plan, UAT, AI evals) and launch-gtm (beta exit, go/no-go). If testing-related prompts misroute in practice, promote a dedicated `release-validation` skill and move those references under it.

## Frameworks inside (menu-style — each skill helps you choose)

Discovery: Mom Test interviewing, Jobs to Be Done, Opportunity Solution Trees, assumption mapping. Positioning: April Dunford's five components, TAM/SAM/SOM, Porter's Five Forces, battle cards. Strategy: Product Vision Board, Playing to Win, DHM, North Star. Prioritization: RICE, ICE, WSJF, Kano, MoSCoW, Now/Next/Later. Requirements: Lean Canvas, Amazon PR-FAQ, lean one-pager/PRD, user stories with Given/When/Then. Delivery: Scrum, Kanban, Shape Up. Launch: launch tiering, phased GTM checklist, message house. Measurement: North Star, AARRR, HEART, OKRs, A/B experimentation.
