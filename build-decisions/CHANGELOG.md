# Changelog

The footer of every census names the version that produced it.

## 0.3.2 (2026-10-16)

- **The report standard is shared.** The shape this census reports in (the count, why it matters, each rule with what goes wrong and a one-minute check, then "Before you change any of these") is now the standard every free plugin follows: `free-plugin-standard/STANDARD.md`. The census report does not change.
- **Evals:** six checks now come from the shared pack (`free-plugin-standard/pack.json`), stamped into each case by `sync_graders.py`. The four census checks the pack repeats were removed, so each case holds one copy. The clean-looking and stop-line cases now also check for fix prompts and code words, and the "fix it too" case checks the full report shape. On the saved reports, every 0.3.1 report passes the shared checks; the new alarms are all on older releases.
- **Credits:** the ASD-STE100 line no longer credits another skill. No text was copied from it.

## 0.3.1 (2026-10-15)

- **Diagnose, never prescribe.** The "To fix" line is gone. In its place: "Before you change any of these", with one question for your AI tool that ends "Change nothing.", and the Free Assessment link (no link when the stop-line is ticked). A new rule says the census never gives fix steps, code, a prompt that changes the app, or an offer to make changes, even when you ask it to fix things. Choosing the real copy and changing the others safely needs judgment; a generic "put it in one place" prompt could make an AI tool drop the server's copy of an access rule.
- **Evals:** checks for the new line, against fix prompts and offers to fix, and against unfilled `<…>` placeholders, on every case with planted pairs and on the "fix it too" case. The new-line and no-fix-prompt checks failed on the saved 0.3.0 reports.

## 0.3.0 (2026-10-15)

- **A report that says what is at risk.** It opens with how many rules your app writes in more than one place, then one fixed line on why that matters: a change can land in one copy and miss the others, and the app then does things you don't expect. Each rule follows with how many places hold it, each place as a plain sentence with its file at the end, what you would see if the copies get out of sync, and a one-minute check. A "To fix" line gives a prompt for your AI tool. The "Screen:/Server:" labels are gone, and nothing comes before the title.
- **Evals:** the planted-pair checks now match any bullet that names the file, and new checks require the count line, the "why this matters" line, an "if they get out of sync" line and the "To fix" line on every case with planted pairs. All four new checks failed on every saved 0.2.1 report.

## 0.2.1 (2026-10-15)

- **Written for founders who don't code.** The report now speaks to an ordinary adult who built the app with an AI tool and does not read code. Each place is described by what it does in the app ("hides the Suspend button for the owner"), not by how the code does it. Programming words (function, helper, constant, endpoint, schema, query and the like) are not used outside file paths. Every check is done in the running app, or is a plain question to ask your AI tool, never a database console.
- **Evals:** a new check on the seeded, crowded, clean-looking, shared-constant and shared-helper cases fails a report that uses programming words outside file paths. It failed 1 of 3 shared-helper runs on 0.2.0.

## 0.2.0 (2026-10-15)

- **A short analysis, not an inventory.** The report is now a few lines: how many decisions are made in two places, one block per decision (the two places, a one-minute check), at most two "worth a look" lines, what was not checked, and the next step. The per-place lists and long fixed sections are gone. A typical report is under 30 lines.
- **It searches your code.** Starting from the helper's places, the agent searches and reads the app (read-only, at most 120 lines at a time, at most 40 searches and reads) to see where each rule or value is defined and whether two places share one source. It used to read only 31 lines around each place. Instruction files, `.env` files, lockfiles and build folders are still never opened.
- **Cards mean own copies.** A decision is reported when two places each hold their own copy of the rule or value, whether or not they differ today; the check finds out.
- **Evals** retargeted to the new report: a length limit, no long sections, the "not checked" line, and safety checks for the wider reading (never open instruction or `.env` files, at most one shell command, at most 40 reads and 40 searches, every read limited to 120 lines, every search file-names-only with the code-file list, and every read and search inside the app with no `..`). The planted-pair checks look only at card lines. Two fixtures were made unambiguous.

## 0.1.2 (2026-10-15)

- **Plain English.** The census is written in ASD-STE100 Simplified Technical English, applied the way Matt Pocock's `/wait-what` skill (MIT) does: a short line of context first, one idea per sentence, at most 25 words a sentence (20 for an instruction), active voice, and the same small set of words every time (place, decision, card, one source, found, read). Long lists became bulleted lists. Checks by hand are short steps.
- **Fixed text rewritten to the same rules:** what the census can't tell you, the stop-line question and footer, and the one prompt.
- **Evals:** two new graders on the seeded, crowded and clean-looking cases. No sentence may run over 25 words, and the context line must come first.

## 0.1.1 (2026-10-15)

- **Fewer false cards.** Two places that read the same shared list, constant or helper (defined once and imported) are one source, not two answers: the census lists them with a one-line note and makes no card. Found on a real app, where two of three cards were pairs like this. A new eval case, `shared-constant-app`, holds it: one shared list that must not be carded beside a real duplicated price that must be. A second case, `shared-helper-diverges`, checks the other side: two places that import one shared price or helper and each add their own discount or filter are still carded.
- **Wording.** Notes about the places read say what they are ("counts and layout, not prices") instead of "none".

## 0.1.0 (2026-10-15)

First release.

- **Census.** It lists every place this run finds where an app decides who can see a record, what something costs, whether someone has paid, and how money rounds. Each decision found in more than one place gets a two-answer card with a check you can run by hand. The census never says the app is clean.
- **Helper.** `census_scan.py` walks the app with custody-check's walk rules and never-open list. It prints one JSON line with paths, line numbers and fixed pattern names only, never text from inside a file. File names with unusual characters are held back and counted.
- **Bounded reading.** The agent reads up to 24 windows of 31 lines around listed places, and nothing else in the app.
- **Stop-line.** Sensitive field names in schema files (`card_number`, `date_of_birth` and the like), or the founder's answer, make the census say **Get a person**, with no booking link.
- **Tests.** Unit tests, a never-miss and noise test that compares every later version with the released one, and eight `claude plugin eval` cases run three times each before release.
