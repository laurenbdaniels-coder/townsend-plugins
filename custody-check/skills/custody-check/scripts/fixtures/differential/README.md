# Differential corpus

`cases.json` holds realistic files and every input a review has found, with the answers the **released**
scanner gave on them. `NeverWorseThanMainTests` runs the current scanner on the same files and fails when:

- an answer (Q1, Q3, Q9) becomes more trusting (toward Nothing found), unless the case is in `ALLOW_SOFTER`;
- a new No appears, unless the case is in `ALLOW_NEW_NO` with the reason the baseline was wrong. A "new alarm"
  means a new No: Nothing found -> Don't know is the cautious direction and needs no listing;
- the scan is partial where the baseline finished;
- the Q10 fields differ.

`ALLOW_SOFTER` is empty: since 0.3.3, 0.3.2 runs underneath every scan (`custody_scan_0_3_2.py`) and the overlay
can only move an answer toward caution, so a softer answer is a bug. `OverlayContractTests` also checks, case by
case, that 0.3.2's rows, partial flag, stats and other questions survive the overlay unchanged.

Keys are stored as `{KEY}` / `{PEM}` / `{PEM_BODY}` placeholders and filled in at run time, so no key-shaped text
is in the repo.

A case is `{"name", "files"}` plus, optionally:

- a file body `{"repeat": text, "times": n}`, written at run time (a 600 KB file costs a few bytes here);
- `"args"`: scan keyword arguments (`{"max_files": 2}`), passed to the baseline as CLI flags (`--max-files 2`);
- `"links"`: `{new path: existing path}` hard links.

- **Add a case** to `build_cases.py` for every input a review finds, then regenerate. Never edit `cases.json` by hand.
- **Regenerate after each release**, from the released scanner, so the baseline moves forward:

      git show <release-tag-or-sha>:custody-check/skills/custody-check/scripts/custody_scan.py > /tmp/baseline.py
      python3 build_cases.py /tmp/baseline.py cases.json "custody-check <version> (<sha>)"
