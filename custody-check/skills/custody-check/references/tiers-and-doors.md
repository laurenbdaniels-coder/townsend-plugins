# Tiers, the stop-line, the doors

Everything here is on the handout. Nothing here decides which gates run for you in what order; that is the routing the studio keeps.

## Tier of the next change

The tier is a property of the **next change**, not of the app. Blast radius, not file count. Tier up when unsure.

| Tier | What it is | Gates to run |
|---|---|---|
| **Light** | one file, reversible, touches no data or config | Build, Verify |
| **Standard** | a feature, two or more files, or anything with a UI | Define, Audit, Plan, Plan review, Build, Verify, Diff review |
| **Gated** | touches any escalation trigger below | everything in Standard plus a security review |

**Escalation triggers (any one makes the change Gated):** auth or sessions; user data; payments; secrets; dependencies; deploy; the schema or a migration; webhooks; background jobs; file uploads; security rules; email; AI prompts or tools; the model or provider (including swapping a model version, changing a prompt that is in production, or turning on training of any kind).

The nine gates, names only: Define, Audit, Plan, Plan review, Build, Verify, Diff review, Ship, Watch.

## If AI drives part of the product

Six more failure modes live in `questions.md` (A1 to A6): the latency budget, where prompts live, whether production is running what was actually tested, whether an eval exists and is judged on examples nobody tuned against, what the user sees when the model is wrong, and whether anyone would notice the model or the product moving underneath. They bite at Plan, Diff review, Ship, Verify, Build and Watch respectively.

They do not change the tier and they do not change the door. The door is the eleven. What they change is the Don't-know list, which is the part the founder leaves with.

Three of them have a training-shaped version (skew, leakage, label decay) for the rare founder who trains or fine-tunes. The concern is the same either way: a model is a moving part inside the product, and nothing turns red when it wanders.

## The stop-line

Any of these ticked means: get a person who does this for a living before the next change ships. The tool prints "Get a person" above the doors and chooses no door.

- payments or card details
- health data
- other people's sensitive personal data, especially children's
- real scale, real money, or a contract riding on uptime

The founder ticks the stop-line in the answers block (`stop_line:`). Scanner evidence on Q10 that shows fields such as `ssn`, `social_security`, `dob`, `date_of_birth`, `birthdate`, `medical`, `diagnosis`, `credit_card`, `card_number`, `cc_number`, `iban`, or `passport` also raises it.

## Three doors

- **Ship it.** It clears the gates. Start small; watch.
- **Patch it.** Three specific things, then ship deliberately.
- **Shelve it.** Rebuild from it; the prototype is now the spec.

### Door rule (applied in this order)

1. Stop-line ticked → print **Get a person** above the doors; choose no door.
2. Q1 = no, Q2 = no, or Q3 = no → **Patch it** (a founder who says the browser calls the database or the AI provider with a privileged key has answered Q1's question).
3. Two or more of Q4, Q5, Q6, Q9 are no or Don't know → **Patch it**.
4. Otherwise → **Ship it**.

Shelve it is never chosen by the tool; it is the founder's call, and the verdict says so when the Patch list would be longer than three items.

### Patch-list order

At most three items, in this order: Q1, then Q2, then Q3, then whichever of Q4, Q5, Q6, Q9 failed, in that order. When the scan was partial and Q1 or Q3 is still Don't know, the door is never Ship it: the verdict prints the rerun recipe (`--max-files 50000`, or point at the app subfolder) above the doors instead. Each item is one sentence naming the by-hand test from `questions.md` and, for Q1, the words "rotate it now".

## Five, if you'll only do five

| # | The five | Mapped questions | Dropped only when |
|---|---|---|---|
| 1 | Classify the change against the Gated list | (tier step) | never |
| 2 | Boundary test: logged out, wrong user, right user; API, database, files | Q3, Q4 | both yes, any confidence |
| 3 | One deployed end-to-end path, including any job, webhook, email, or AI call | (always kept) | never |
| 4 | Read the diff for surprises | Q7 | yes, any confidence |
| 5 | Prove rollback and one real alert | Q5, Q9 | both yes, any confidence |

Items 1 and 3 are always printed. The others print unless every mapped question is yes.

## Why a scanner no cannot be argued down, and a scanner yes can be raised

A scanner **no** is positive evidence: a key-shaped value where the browser can read it, a table with its row security switched off. The founder's answers never override it; the fix is to rotate or close the thing, then re-run. A scanner **yes** is an inference from file names and history (a deploy config exists, two environments are named) and renders at **medium** confidence; the founder raises it to **high** by confirming the thing has actually been done once.
