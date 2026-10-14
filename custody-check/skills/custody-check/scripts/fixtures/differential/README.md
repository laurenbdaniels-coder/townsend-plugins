# Differential corpus

`cases.json` holds realistic files and every input a review has found. `NeverWorseThanMainTests` runs the
current scanner and **released main** on the same files and fails when:

- an answer (Q1, Q3, Q9) becomes more trusting (toward Nothing found), unless the case is in `ALLOW_SOFTER`;
- a new No appears, unless the case is in `ALLOW_NEW_NO` with the reason the baseline was wrong. A "new alarm"
  means a new No: Nothing found -> Don't know is the cautious direction and needs no listing;
- the scan is partial where the baseline finished;
- the Q10 fields differ;
- the output shows a sentinel (`hunter2`, hidden inside a string, a function body or a quoted name) that the
  released scanner did not show on the same files (`test_never_prints_text_the_baseline_did_not`).

**The floor is released main** (from 0.3.4 on). The tests export the release's whole `scripts/` folder with
`git archive` at `git merge-base HEAD origin/main` (every merge to main is a release) and run it in-process beside
the branch; `CUSTODY_RELEASE_REF=<ref>` pins another ref (a reviewer reproducing "main vs branch" on an older
release). CI checks out full history (`fetch-depth: 0`) and sets `CUSTODY_REQUIRE_GIT=1`, so a release that cannot
be exported fails the run. A copy without git history falls back to the answers stored in `cases.json`.

The base scanner (`custody_scan_0_3_2.py` and the overlay) may be edited when the corpus shows equal-or-more caution.
Anything less cautious, or a new No, is listed in `ALLOW_SOFTER` / `ALLOW_NEW_NO` with the reason the release was
wrong (both are empty today). A PR that edits `custody_scan_0_3_2.py` re-freezes it in the same PR: update
`RELEASE_SHA256` (sha256 of the text with `\r\n` read as `\n`) and the frozen-file test. `OverlayContractTests`
checks, case by case, that 0.3.2's rows, partial flag, stats and other questions survive the overlay unchanged.

Keys are stored as `{KEY}` / `{PEM}` / `{PEM_BODY}` placeholders and filled in at run time, so no key-shaped text
is in the repo.

A case is `{"name", "files"}` plus, optionally:

- a file body `{"repeat": text, "times": n}`, written at run time (a 600 KB file costs a few bytes here);
- `"args"`: scan keyword arguments (`{"max_files": 2}`), passed to the baseline as CLI flags (`--max-files 2`);
- `"links"`: `{new path: existing path}` hard links.

- **Add a case** to `build_cases.py` for every input a review finds, then regenerate. Never edit `cases.json` by hand.
- **Regenerate after each release**, so the stored audit copy names the new release (from the repo root):

      python3 custody-check/skills/custody-check/scripts/fixtures/differential/build_cases.py origin/main \
          custody-check/skills/custody-check/scripts/fixtures/differential/cases.json

  It exports the release's `scripts/` folder (`git archive <ref> custody-check/skills/custody-check/scripts`), not
  one file: since 0.3.3 `custody_scan.py` loads `custody_scan_0_3_2.py` from its own folder, so a lone copy only
  answers `internal:release-missing`. The label (`custody-check <version> (main <sha>)`) and `baseline_sha` are
  written for you; `test_the_corpus_baseline_is_what_its_release_says` checks the stored answers against that sha.
  Then remove any `ALLOW_NEW_NO` / `ALLOW_SOFTER` entry the release now gives (the stale-entry check names them).
