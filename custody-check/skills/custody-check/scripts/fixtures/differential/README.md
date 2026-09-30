# Differential corpus

`cases.json` holds realistic files and every input a review has found, with the answers the **released**
scanner gave on them. `NeverWorseThanMainTests` runs the current scanner on the same files and fails when
an answer becomes more trusting (toward Nothing found) or a new No appears, unless the exception is listed
in the test with the reason the baseline was wrong.

Keys are stored as `{KEY}` / `{PEM}` placeholders and filled in at run time, so no key-shaped text is in
the repo.

- **Add a case** to `build_cases.py` for every input a review finds, then regenerate.
- **Regenerate after each release**, from the released scanner, so the baseline moves forward:

      git show <release-tag-or-sha>:custody-check/skills/custody-check/scripts/custody_scan.py > /tmp/baseline.py
      python3 build_cases.py /tmp/baseline.py cases.json "custody-check <version> (<sha>)"
