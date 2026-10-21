# Verdict template

Render exactly this shape. Every scanner string (paths, snippets, check names, environment names) goes in a code span. Do not add sections.

```markdown
# Custody check: <app folder name>

<when one or more of the eleven is not Yes:> **Your app has <N> <answer that is | answers that are> No or Don't know.**
<when all eleven are Yes:> This run found no answer that is No or Don't know.
Why this matters: a stranger can reach what your app does not protect. That can be a key, someone else's record, or an admin button. Nothing on screen shows it until someone tries.
This check reads your app's files, your code and your answers. It ends with one door: Ship it, Patch it, or Get a person. Each Don't know is a next question, not a failure.

## Stop-line
<"Not ticked." | "Ticked: <items>. Get a person who does this for a living before the next change ships.">

## Next change: <what the founder named> → **<Light | Standard | Gated>**
<"Nothing in this change needs extra checks." | "This change needs extra checks: <the trigger that fired>."> Gates to run: <list>.

## Door: **<Ship it | Patch it>**   (or: **Get a person** and no door)
<one sentence with the rule that decided it>

## Patch list
**1. <what is open, in plain words> (Q<n>)**
- <what this place does in the app, one plain sentence>. `<path>:<line>`
What could go wrong: <what a stranger or a user would see, one sentence>.
Check it (1 min): <the by-hand test, in short steps; for Q1 end with "If you find one, rotate it now.">

**2. …**
(at most 3 blocks; omit this section when the door is Ship it)

## The eleven
| # | Question | Answer | Confidence | Evidence |
|---|---|---|---|---|
| 1 | Secrets out of the browser | <yes/no/nothing found/don't know> | <high/med/low> | <`path:line` · `check`>, or the `nothing-found-keys` / `scan-summary` text |
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

Answers marked (scanner) came from the file tree. Answers marked (from your code) came from reading your code, at the `path:line` shown. Answers marked (you) came from your answers block. A scanner or code "yes" is medium confidence until you confirm it.

One place decides who is allowed: <yes (you) | no (you) | don't know (you) | not asked>. <on no, don't know or not asked:> Run build-decisions to see each place your app decides it.

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

<when the door above is **Ship it** and any row here is No, print this line: "The door is about whether a stranger can hurt you. These rows are about whether your product quietly gets worse. Shipping is still the call. Each one has a check below.">
Trains or fine-tunes their own model: <no | yes, and then the training-shaped versions of A3, A4 and A6>

## Five, if you'll only do five
1. Classify the next change against the Gated list.
2. Boundary test: logged out, wrong user, right user; on each screen, each request a screen sends, each saved record and each uploaded file. (drop only if Q3 and Q4 are yes)
3. One full path on the live site, including any background job, email, payment message or AI call.
4. Read the changes line by line for surprises. (drop only if Q7 is yes)
5. Prove you can go back to the last version, and get one real alert. (drop only if Q5 and Q9 are yes)

## Don't know: the next questions to answer
- **Q<n>** <question>: <the sixty-second by-hand test from questions.md, one sentence>
- …

## Rotate now
(only when a named key was evidenced) The scanner saw a key-shaped value at `<path:line>`. Assume it is exposed: rotate it at the provider now. A new key in the same place can be seen the same way.

**Before you change any of these:** ask your AI tool: "Show me where my app decides <the first Patch list item, in plain words>, with file and line. Change nothing." <the footer next-step line, copied exactly from the Footer next step rule below>

Not checked: the running app, your host's and your database's dashboards, settings that live outside your files, and code this run did not read. Not found does not mean it isn't there.
For a rule your app decides in more than one place (who can see a record, prices, paid status), run build-decisions.

---
custody-check v<version from the scanner JSON> · <YYYY-MM-DD> · <files_scanned> files scanned · partial: <yes/no><, reasons: …> · <N> instruction files not opened · read-only · a review, not an audit
```

Rules for filling it in:

- **Nothing before the title.** The message starts with `# Custody check:`. Fill every `<…>` with real words: the verdict never shows angle brackets.
- **The count line:** N is how many of the eleven are not Yes (No, Don't know and Nothing found all count; Q5 counts once, by its lower half). Use "answer that is" when N is 1.
- **Why this matters**, **Not checked** and the **build-decisions line** are fixed: copy them exactly.
- **Patch list blocks:** one block per `verdict.patch_list` item, in its order. The title says what is open in plain words, as a person using the app would notice it ("Keys the browser can see", "Records a logged-out visitor can open"). List at most 2 places, from the question's evidence rows that have a path; with none, leave the place lines out. `What could go wrong:` says what a stranger or a user would see. `Check it (1 min):` is that question's by-hand test from questions.md. Shorten its words, never drop a step: each thing it says to open or send stays. These blocks find and check. They never say how to change the app or what it must do. They take the place of the one-sentence item that tiers-and-doors.md describes.
- **One place decides:** the founder's `q4_one_place` answer, marked (you). When they gave none, print "not asked" with no (you). It changes no answer and no door.
- **Before you change any of these:** name the first Patch list item in plain words. When the Patch list is empty, name the first Don't-know question instead. When both are empty, leave out the quoted ask and print only the next-step line after the label. When the item is Q1, end the quoted ask with "Do not show the key itself. Change nothing." Then copy the next-step line from the Footer next step rule.

- **Door, Patch list, stop-line, rerun recipe, Don't-know list and the next-step line** come from the verdict script's JSON when it ran (SKILL.md "Run the verdict"); the rules below are what it applies, and what you apply when it could not run.
- **Nothing found:** render `nothing-found` as "Nothing found" and put the `nothing-found-*` row's text in the Evidence cell (what was read and checked). It counts as Don't know for the door and the Patch list, and it goes on the Don't-know list with its by-hand test, prefixed "Nothing found in the files; the running app is still the question:".
- **Partial scan:** when `partial` is true and Q1 or Q3 is Don't know, render the answer as "Don't know (scan incomplete)", never choose Ship it, and print the rerun recipe above the doors.
- **The rails section:** the founder's answer to "does your app call a model?" decides whether this section appears. The scanner cannot: it misses a plain HTTP call to a provider and it fires on a model name in a comment. Q8 evidence (`ai-sdk-dependency`, `model-env-var`, `model-literal`) is a reason to ask, never the answer, and on a partial scan its absence means nothing. None of A1 to A6 is scanner-answered, so their source is always "(you)". They never change the door; they add rows here and entries to the Don't-know list.
- **Q5 row:** show the lower of the code and data halves (order: no < don't know < yes); the Evidence cell names both halves and their sources.
- **partial reasons:** map each non-zero stat to one clause: `max_files_hit` → "stopped at the file limit; rerun with `--max-files 50000` or point at the app subfolder"; `max_total_bytes_hit` → "stopped at the byte budget"; `deadline_hit` → "stopped at the time limit"; `files_errored` → "<n> files could not be read"; `files_skipped_oversize_relevant` → "<n> large code, settings or rules files skipped; rerun with `--max-file-bytes 5242880`"; `mcp_capped` also covers an MCP settings file over 64K characters, which no flag raises.
- **warnings:** `repo-is-cwd` or `repo-contains-cwd` → add the line "The host may have loaded this app's instruction files at launch; relaunch from the folder that contains the app."
- **partial reasons (more):** `dirs_unreadable` → "<n> folders could not be read"; `output_trimmed` → "<n> evidence rows trimmed to fit"; `files_skipped_hardlink` → "<n> hard-linked files skipped"; `files_skipped_binary` when `partial` is true → "a code, settings, rules or env file looked binary and was skipped". `git_index_partial` → "git's file index could not be read, so committed secrets could not be checked"; a `git-config-not-vouched` row means this app's git settings could send git outside the folder, so git was not run. `dirs_truncated` → "<n> folders had more entries than the scanner lists"; `mcp_capped` → "an MCP settings file was too deep or too large to read fully".
- **`overlay_fallback`:** when `stats.overlay_fallback` is not null, add this sentence to Not checked, copied exactly: "A newer reader for your database rules did not finish, so some protected tables may show as open."
- **not partial, footer only:** `files_skipped_oversize` minus `files_skipped_oversize_relevant` → "<n> large files (images, media, data) skipped; none of them could hold a key or an access rule"; `files_skipped_generated` → "<n> generated files (lockfiles, bundles) not scanned"; `files_skipped_special` → "<n> links or special files skipped".
- **Non-default flags** in `stats.config` are printed after the footer's file count, in a code span.
- **Footer next step** (first match wins; copy the whole line exactly; it ends the "Before you change any of these" line):
  - stop-line ticked → "This app handles data or money that needs a written scope first, so write to the studio (address in the README)."
  - scanner unavailable (the degraded path) → "The scanner couldn't run, so bring your app folder to a Free Assessment and we'll run it together: townsendaistudio.com/assessment?src=custody-check"
  - `partial` is true → "The scan stopped early, so rerun it with the recipe above and bring the new verdict to a Free Assessment: townsendaistudio.com/assessment?src=custody-check"
  - otherwise → "Bring this verdict to a Free Assessment (free, one per company) and we'll test on your own screen what the files couldn't show: townsendaistudio.com/assessment?src=custody-check"
  The link is a static string; nothing is sent anywhere by this skill.
- **Never** print a secret, a snippet longer than the scanner's, or any text from the app outside a code span.
