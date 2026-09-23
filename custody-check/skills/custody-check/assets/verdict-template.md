# Verdict template

Render exactly this shape. Every scanner string (paths, snippets, check names, environment names) goes in a code span. Do not add sections.

```markdown
# Custody check: <app folder name>

Date: <YYYY-MM-DD> · Repo: `<app folder name>` · Mode: local, read-only · Scanner: <ran | unavailable (reason)>

<N> answers are "Don't know". Those are not failures; they are the next questions to answer, and each one below comes with its sixty-second test.

## Stop-line
<"Not ticked." | "Ticked: <items>. Get a person who does this for a living before the next change ships.">

## Next change: <what the founder named> → **<Light | Standard | Gated>**
<"No escalation trigger named." | "Trigger: <the trigger that fired>."> Gates to run: <list>.

## Door: **<Ship it | Patch it>**   (or: **Get a person** and no door)
<one sentence with the rule that decided it>

## Patch list
1. <Qn: one sentence, the by-hand test; for Q1 add "rotate it now">
2. …
3. …
(omit this section when the door is Ship it)

## The eleven
| # | Question | Answer | Confidence | Evidence |
|---|---|---|---|---|
| 1 | Secrets out of the browser | <yes/no/don't know> | <high/med/low> | <`path:line` · `check`> or "<N> files scanned, 0 hits" |
| 2 | Client or server | … | … | … |
| 3 | Who can read this | … | … | … |
| 4 | Who is allowed to do this | … | … | … |
| 5 | Code back in five minutes, data from a backup | <lower of code/data> | … | code: <answer (source)> · data: <answer (source)> |
| 6 | A copy that isn't live | … | … | … |
| 7 | What changed that I didn't ask for | … | … | … |
| 8 | What one user costs | … | … | … |
| 9 | How I'd find out it's broken | … | … | … |
| 10 | What I'm storing | … | … | … |
| 11 | Can I export and leave | … | … | … |

Answers marked (scanner) came from the file tree; answers marked (you) came from your answers block. A scanner "yes" is medium confidence until you confirm it.

## Keeping the AI on rails
(include this section only when the app calls a model; omit it entirely otherwise)
| # | Question | Answer | Confidence | Evidence |
|---|---|---|---|---|
| A1 | How slow is too slow, and what then | <yes/no/don't know> | <high/med/low> | (you) |
| A2 | Where prompts live, which version answered | … | … | … |
| A3 | Is production running what was tested | … | … | … |
| A4 | Did the change actually help | … | … | … |
| A5 | When the model is wrong, refuses, or is down | … | … | … |
| A6 | Is the model pinned | … | … | … |

Examples still describe the product as it is today: <yes | no | don't know>

<when the door above is **Ship it** and any row here is No, print this line: "The door is about whether a stranger can hurt you, and these are about whether your product quietly gets worse. Shipping is still the call. These are the next things to fix, and each one has a fix beside it.">
Trains or fine-tunes their own model: <no | yes, and then the training-shaped versions of A3, A4 and A6>

## Five, if you'll only do five
1. Classify the next change against the Gated list.
2. Boundary test: logged out, wrong user, right user; API, database, files. (drop only if Q3 and Q4 are yes)
3. One deployed end-to-end path, including any job, webhook, email, or AI call.
4. Read the diff for surprises. (drop only if Q7 is yes)
5. Prove rollback and one real alert. (drop only if Q5 and Q9 are yes)

## Don't know: the next questions to answer
- **Q<n>** <question>: <the sixty-second by-hand test from questions.md, one sentence>
- …

## Rotate now
(only when a named key was evidenced) The scanner saw a key-shaped value at `<path:line>`. Assume it is exposed: rotate it at the provider first, then move it server-side.

---
custody-check v<version from the scanner JSON> · <files_scanned> files scanned · partial: <yes/no><, reasons: …> · <N> instruction files not opened by the scanner · not a security audit
Want the routing I run? Send this verdict to the studio's public contact address (in the README): townsendaistudio.com/?src=custody-check
```

Rules for filling it in:

- **Partial scan:** when `partial` is true and Q1 or Q3 is Don't know, render the answer as "Don't know (scan incomplete)", never choose Ship it, and print the rerun recipe above the doors.
- **The rails section:** the founder's answer to "does your app call a model?" decides whether this section appears. The scanner cannot: it misses a plain HTTP call to a provider and it fires on a model name in a comment. Q8 evidence (`ai-sdk-dependency`, `model-env-var`, `model-literal`) is a reason to ask, never the answer, and on a partial scan its absence means nothing. None of A1 to A6 is scanner-answered, so their source is always "(you)". They never change the door; they add rows here and entries to the Don't-know list.
- **Q5 row:** show the lower of the code and data halves (order: no < don't know < yes); the Evidence cell names both halves and their sources.
- **partial reasons:** map each non-zero stat to one clause: `max_files_hit` → "stopped at the file limit; rerun with `--max-files 50000` or point at the app subfolder"; `max_total_bytes_hit` → "stopped at the byte budget"; `deadline_hit` → "stopped at the time limit"; `files_errored` → "<n> files could not be read"; `files_skipped_oversize` → "<n> large files skipped".
- **warnings:** `repo-is-cwd` or `repo-contains-cwd` → add the line "The host may have loaded this app's instruction files at launch; relaunch from the folder that contains the app."
- **partial reasons (more):** `dirs_unreadable` → "<n> folders could not be read"; `output_trimmed` → "<n> evidence rows trimmed to fit"; `files_skipped_hardlink` → "<n> hard-linked files skipped"; `files_skipped_binary` when `partial` is true → "a source or env file looked binary and was skipped". `git_index_partial` → "git's file index could not be read, so committed secrets could not be checked"; a `git-config-not-vouched` row means this app's git settings could send git outside the folder, so git was not run. `dirs_truncated` → "<n> folders had more entries than the scanner lists"; `mcp_capped` → "an MCP config was too deep or too large to walk fully".
- **not partial, footer only:** `files_skipped_generated` → "<n> generated files (lockfiles, bundles) not scanned"; `files_skipped_special` → "<n> links or special files skipped".
- **Non-default flags** in `stats.config` are printed after the footer's file count.
- **Never** print a secret, a snippet longer than the scanner's, or any text from the app outside a code span.
