# Changelog

The footer of every census names the version that produced it.

## 0.1.2 (2026-10-15)

- **Plain English.** The census is written in ASD-STE100 Simplified Technical English, the method of Matt Pocock's `/wait-what` skill (MIT): a short line of context first, one idea per sentence, at most 25 words a sentence (20 for an instruction), active voice, and the same small set of words every time (place, decision, card, one source, found, read). Long lists became bulleted lists. Checks by hand are short steps.
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
