# Tiers, the stop-line, the doors

Everything here is on the handout. Nothing here decides which gates run for you in what order.

The report (0.6.0 on) prints none of this: no tier, no door, no stop-line word. The verdict script still applies the door rule, and the report uses its stop-line and rerun fields. The tiers, the doors and the five stay in the workshop and the README.

## Tier of the next change

The tier is a property of the **next change**, not of the app. Blast radius, not file count. Tier up when unsure.

| Tier | What it is | Gates to run |
|---|---|---|
| **Light** | one file, reversible, touches no data or config | Build, Verify |
| **Standard** | a feature, two or more files, or anything with a UI | Define, Audit, Plan, Plan review, Build, Verify, Diff review |
| **Gated** | touches any escalation trigger below | everything in Standard plus a security review |

**Escalation triggers (any one makes the change Gated):** auth or sessions; user data; payments, including payments your payment company runs; secrets; dependencies; deploy; how your data is stored (its tables and fields), or any change to it, however small; webhooks; background jobs; file uploads; security rules; email; AI prompts or tools; the model or provider (including swapping a model version, changing a prompt that is in production, or turning on training of any kind).

The nine gates, names only: Define, Audit, Plan, Plan review, Build, Verify, Diff review, Ship, Watch.

## If AI drives part of the product

Six more failure modes live in `questions.md` (A1 to A6): the latency budget, where prompts live, whether production is running what was actually tested, whether a change made things better rather than different, what the user sees when the model is wrong, and whether the provider is about to move them off their model version. They bite at Plan, Diff review, Verify, Verify, Build and Watch respectively, and each one ends with a check the founder can run in the room.

They do not change the tier and they do not change the door. The door is the eleven. What they change is the report's problem blocks and open-question bullets.

Three have a training-shaped version for the rare founder who trains or fine-tunes: skew, leakage, and stale labels. The concern is the same either way. A model is a moving part inside the product, and nothing turns red when it wanders. A seventh note covers the twin of the eval question, which is what happens when the product moves and the examples do not.

## The stop-line

Any of these ticked means: get a person who does this for a living before the next change ships. The verdict script chooses no door, and the report opens with the extra-risk block, a plain fact about what carries the risk and what a mistake costs.

- the app stores or handles card numbers or other card details itself
- the app holds or moves money for other people (payouts, Connect, escrow, stored balances, wallets)
- health data
- other people's sensitive personal data, especially children's
- real scale, or a contract that needs the app to stay up

Payments your payment company runs (checkout, Elements, embedded checkout, subscriptions, invoices, refunds, a billing portal), where it holds the card details and settles the money, are not on this list when that is all the app does with money. It is ordinary Gated work: the payments trigger above. Any other money handling gets one question, and it is ticked when the answer is unclear.

The founder ticks the stop-line in the answers block (`stop_line:`). Scanner evidence on Q10 that shows fields such as `ssn`, `social_security`, `dob`, `date_of_birth`, `birthdate`, `medical`, `diagnosis`, `credit_card`, `card_number`, `cc_number`, `iban`, or `passport` also raises it. The agent's read of your code raises it too, when the code shows one of the first four items above.

## Three doors

- **Ship it.** It clears the gates. Start small; watch.
- **Patch it.** Three specific things, then ship deliberately.
- **Shelve it.** Rebuild from it; the prototype is now the spec.

### Door rule (applied in this order)

The skill's verdict script (`custody_verdict.py`) applies these steps; when it cannot run, the agent applies them by hand.

1. Stop-line ticked → **Get a person**; choose no door (the report shows the extra-risk block instead).
2. Q1 = no, Q2 = no, or Q3 = no → **Patch it** (a founder who says the browser calls the database or the AI provider with a privileged key has answered Q1's question).
3. The scan was partial and Q1 or Q3 is still Don't know → never **Ship it**; the report prints the rerun line and the door is **Patch it**.
4. Two or more of Q4, Q5, Q6, Q9 are no or Don't know → **Patch it**.
5. Otherwise → **Ship it**.

Nothing found counts as Don't know in every step above: it says the scanner looked properly, not that the running app is safe.

Shelve it is never chosen by the tool; it is the founder's call, and the report never mentions it.

### Patch-list order

At most three items, in this order: Q1, then Q2, then Q3, then whichever of Q4, Q5, Q6, Q9 failed, in that order. When the scan was partial and Q1 or Q3 is still Don't know, the door is never Ship it, and the report prints the rerun line (`--max-files 50000`). In the report this order only decides which problem blocks come first.

## Why a scanner no cannot be argued down, and a scanner yes can be raised

A scanner **no** is positive evidence: a key-shaped value where the browser can read it, a table with its row security switched off. The founder's answers never override it; only a new scan, after the thing is rotated or closed, changes it. A scanner **yes** is an inference from file names and history (a deploy config exists, two environments are named) and renders at **medium** confidence; the founder raises it to **high** by confirming the thing has actually been done once.
