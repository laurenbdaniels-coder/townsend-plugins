# Differential corpus

`cases.json` holds realistic files and every input a review has found. `NeverWorseThanMainTests` runs the
current scanner and **released main** on the same files and fails when:

- an answer (Q1, Q3, Q9) becomes more trusting (toward Nothing found), unless `ALLOW_SOFTER` lists the case with
  that exact answer and the reason the baseline was wrong;
- a new No appears, unless the case is in `ALLOW_NEW_NO` with the reason the baseline was wrong. A "new alarm"
  means a new No: Nothing found -> Don't know is the cautious direction and needs no listing;
- the scan is partial where the baseline finished;
- the Q10 fields differ;
- the output shows a sentinel (`hunter2`, hidden inside a string, a function body or a quoted name) that the
  released scanner did not show on the same files (`test_never_prints_text_the_baseline_did_not`).

**The floor is released main** (from 0.3.4 on). The tests export the release's whole `scripts/` folder with
`git archive` at `git merge-base HEAD origin/main` (every merge to main is a release) and run it in-process beside
the branch. On main itself (a CI push to main) that merge-base is HEAD, so the floor is HEAD's first parent, the
release before it: comparing HEAD with HEAD would pass any regression. `CUSTODY_RELEASE_REF=<ref>` pins another ref
(a reviewer reproducing "main vs branch" on an older release); it must name a commit strictly before HEAD, and one
that does not load fails the run. CI checks out full history (`fetch-depth: 0`); the gating Linux job sets
`CUSTODY_REQUIRE_GIT=1`, so a release that cannot be exported fails it (the advisory Windows job does not set it).
A copy without git history falls back to the answers stored in `cases.json`.

The base scanner (`custody_scan_0_3_2.py` and the overlay) may be edited when the corpus shows equal-or-more caution.
Anything less cautious, or a new No, is listed in `ALLOW_SOFTER` / `ALLOW_NEW_NO` with the reason the release was
wrong (`ALLOW_NEW_NO` is empty today; `ALLOW_SOFTER` lists the three credited DO-block loop cases, S-044, 0.6.0). An `ALLOW_SOFTER` entry is `(case, question): (allowed answer, reason)` and excuses
only a move to that answer: softening the same case further later needs the entry edited, whether or not the
release lists it. Once that PR merges, the release gives the answer itself, so the entry goes unused;
the stale-entry check skips any entry the release's own test file still lists (graduated), and fails only on an
entry neither the branch nor the release needs. Remove graduated entries when convenient (the regenerate step). A PR that edits `custody_scan_0_3_2.py` re-freezes it in the same PR: update
`RELEASE_SHA256` (sha256 of the text with `\r\n` read as `\n`) and the frozen-file test. `OverlayContractTests`
checks, case by case, that 0.3.2's rows, partial flag, stats and other questions survive the overlay unchanged.

Keys are stored as `{KEY}` / `{PEM}` / `{PEM_BODY}` placeholders and filled in at run time, so no key-shaped text
is in the repo.

A case is `{"name", "files"}` plus, optionally:

- a file body `{"repeat": text, "times": n}`, written at run time (a 600 KB file costs a few bytes here);
- `"args"`: scan keyword arguments (`{"max_files": 2}`), passed to `scan()` on both the branch and released main,
  and as CLI flags (`--max-files 2`) when `build_cases.py` writes the stored audit copy;
- `"links"`: `{new path: existing path}` hard links.

- **Add a case** to `build_cases.py` for every input a review finds, then regenerate. Never edit `cases.json` by hand.
- **Regenerate after each release**, so the stored audit copy names the new release (from the repo root):

      python3 custody-check/skills/custody-check/scripts/fixtures/differential/build_cases.py origin/main \
          custody-check/skills/custody-check/scripts/fixtures/differential/cases.json

  It exports the release's `scripts/` folder (`git archive <ref> custody-check/skills/custody-check/scripts`), not
  one file: since 0.3.3 `custody_scan.py` loads `custody_scan_0_3_2.py` from its own folder, so a lone copy only
  answers `internal:release-missing`. The label (`custody-check <version> (main <sha>)`) and `baseline_sha` are
  written for you; `test_the_corpus_baseline_is_what_its_release_says` checks the stored answers against that sha.
  Then remove any `ALLOW_NEW_NO` / `ALLOW_SOFTER` entry the release now gives. The stale-entry check does not name
  these (they are graduated: the release's own test file lists them), so look for them by hand.
