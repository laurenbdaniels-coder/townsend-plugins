# Evidence Rules (suite-wide)

These rules bind every skill and artifact in product-flow. They exist because the most expensive failure in product work is a confident claim nobody can trace — and AI assistance makes inventing plausible evidence effortless. The suite must be structurally incapable of it.

## The provenance chain

Every factual claim in any artifact carries one of:

1. **A source line** — `(Source: who/what, date, where — interview, call, metric, document)`. Quotes name the speaker's role and context; metrics name the system and query date.
2. **An `[ASSUMPTION]` tag** — for claims believed but not verified. Assumptions are legitimate; hidden assumptions are not. Every tag states what evidence would confirm or kill it. This is the suite's one tag syntax — use it everywhere a claim lacks a source.
3. **A `TK` placeholder** — for data that exists but isn't in hand. TK means "go get it," never "make it up."

If the user supplies a claim without a source, ask once; if none exists, tag it `[ASSUMPTION]` rather than dropping or silently asserting it.

## Hard rules

- Never fabricate quotes, testimonials, statistics, market sizes, dates, or customer names — not to "make it compelling," not as illustration, not when asked. Offer the `[ASSUMPTION]`/TK mechanism instead and say why.
- The one sanctioned fiction: PR-FAQ-style future testimonials, labeled `[ASPIRATIONAL — replace with real customer voice before stakeholder review]`.
- Synthesis outputs use claim → source → confidence. Confidence: **High** = multiple independent sources; **Medium** = single good source; **Low** = indirect, dated, or uncited.
- Seek disconfirming evidence explicitly: research readouts include a "what we looked for and didn't find" section. Confirmation-only research is advocacy.
- Evidence ages: flag sources older than ~12 months when they anchor a major claim.

## Gate rule (tag-and-warn, never block)

Artifacts headed to leadership, investors, or external audiences should not carry unresolved `[ASSUMPTION]` tags on load-bearing claims. When they do, don't refuse and don't silently strip them — surface them in an explicit "Open assumptions & risks" section and warn the user plainly that the doc argues from assumption. A hard ready/not-ready verdict is artifact-critique's job, nobody else's.

## Cheap evidence first

`[ASSUMPTION]` is the fallback, not the first move. Before tagging: check data the user already mentioned, run a quick web search for public benchmarks (cited in the provenance format), or ask for the one number the user probably has. When a claim can be upgraded from assumed to sourced with reachable effort, upgrade it now — and for what remains, propose the cheapest test that would convert each tag.

## Writing that can't hallucinate

- No weasel words — "significant," "many," "several," "substantially," "dramatically" — replace with the number or the specific impact ("several teams" → "4 teams"). A document that cannot say "significant" must find the number.
- Every metric gets context: "activation 34% (target 30%)," never a bare number.
- Show, don't tell: "customers tapped three times across two pages to remove one item" beats "customers found it slow."
- No hyperbole ("game-changing," "revolutionary") — grounded and self-critical over self-congratulatory.
- Missing data → TK. Never an invented figure.
