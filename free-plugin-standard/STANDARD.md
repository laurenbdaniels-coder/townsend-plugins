# The free-plugin report standard

What each free plugin does and doesn't do is decided in `SCOPE.md`; this file is the report shape. When the two disagree, SCOPE.md wins.

Every free Townsend plugin that checks an app reports to this standard (spell-it-out, which only changes how Claude asks questions, is outside it). Reference implementations: custody-check 0.6.0 (`custody-check/skills/custody-check/assets/verdict-template.md`) and build-decisions 0.6.0 (`build-decisions/skills/build-decisions/SKILL.md` Step 5).

## The reader

The reader built their app by prompting an AI tool. They are an ordinary adult who does not read or write code. They know the app by its screens, buttons, plans and prices. Every sentence must make sense to them without a programmer next to them.

## The no-fix line

A free plugin **finds and explains**. Its report says what is broken and what it means for the reader, and nothing to do (Lauren, 2026-10-21): no check to run, no do-this-next line, no link and no pointer to the other plugin. custody-check from 0.6.0 and build-decisions from 0.6.0 follow it.

It never gives fix steps, code, a prompt that changes the app, a question for the reader's AI tool, or an offer to make changes, now or in another conversation. That holds even when the reader asks for a fix. The one safety step is "replace it now" for a key that may be exposed.

A generic fix prompt is unsafe: an AI tool can drop the server's copy of an access rule.

## The report, in order

1. **Title.** Nothing comes before it.
2. **The count**, one bold line. build-decisions: `**Your app has N <rules that are written in more than one place>.**`, with `, and M <values the browser chooses>` added when it found any (or only that clause when it found no rule), or one plain line when nothing is found ("This run found no ..."). custody-check: `**We found N problems in your code, and M things your code can't tell us.**`, with "no" for zero.
3. **Why this matters:** one fixed line, the risk in everyday terms (what breaks, what the user sees).
4. **The coverage line:** how many code files the run read to the end, one of three fixed forms ("We read all <m> of your code files.", "We read <n> of your <m> code files. Problems in the others can be missed.", "We read <n> code files. Problems in files we did not read can be missed.").
5. **The extra-risk block**, only when the stop-line is ticked: what the app keeps or does, and what a mistake costs. A plain fact, never advice, not counted.
6. **Each issue** (at most 4, then "And N more"): a numbered bold title in plain words, then `What it means for you:` (what the reader would see go wrong). build-decisions lists each place as one plain sentence ending in `path:line`; custody-check ends the block with `Where:`. custody-check also prints "Do today" when a key was seen.
7. **Warnings** (build-decisions only, optional): when the run found any, a bold heading with their own number (`**1 warning:**`, `**N warnings:**`), not counted in the count line, then numbered blocks of their own (title, one places sentence, `What it means for you:`), at most one in full, then "And N more warnings." No warnings prints nothing.
8. **What it could not settle:** build-decisions' "Also worth a look" (at most 2 lines); custody-check's open questions.
9. **Not checked:** one fixed line that names what the run did not look at and ends "Not found does not mean it isn't there", then any short fixed lines that apply (stopped early, no search tool). A free plugin never says the app is clean.
10. **Footer**, after a `---` line: `<plugin> v<version> · read-only · a review, not an audit`. Nothing follows it but the plugin's allowed questions (in build-decisions 0.6.1 and later, when the host cannot ask the stop-line question before the report, a yes after the footer prints the extra-risk block on its own; from 0.6.2, a plain yes first gets one follow-up question, "Which of these?").

The per-issue lines use these exact words, with two kinds of exception in `pack.json`. A plugin may give its own `words` for a grader listed in `plugin_words`: the risk line, as a plain label ending in a colon ("out of sync" fits copies of a rule and not an open key), and the count line, as one bold line that starts with a word. A plugin may `omit`, with a reason, a grader listed in `omittable` (only `std-check-it`, kept for older releases). The no-fix line (no fix prompt, no code words) can never be reworded or left out. `sync_graders.py` checks each shape. A plugin whose issues need other words changes this standard, and the shared graders, in a pull request. It does not loosen its own graders.

custody-check 0.6.0 and later has its own plain shape: count, why, a coverage line, an extra-risk block when its stop-line is ticked, a Do today line when a key was seen, the issue blocks under "What we found in your code" (bold title, What it means for you, Where), the open questions under "What your code can't tell us", a not-checked line, the footer. The door, the eleven, the tier and the five stay in the workshop and its README, not in the report.

## Plain English

- ASD-STE100 Simplified Technical English. One idea per sentence. Active voice, present tense, common words.
- At most 25 words in a sentence, at most 20 in an instruction.
- No programming words outside file paths: function, helper, constant, variable, import, endpoint, API, route, component, middleware, schema, migration, query, SQL, console, terminal, boolean, enum, string, array, null, config, regex, props, backend, frontend, codebase, hard-coded, allow-list, refactor.
- Describe each place by what a person using the app would notice, never by how the code does it.
- Analysis, not inventory: no lists of every place found, no explanation of places that are fine.

## Evals

`claude plugin eval` has no include for `case.yaml`, so the shared graders live in `pack.json` and are copied into each case:

- `always`: no fix prompt, no code words, the coverage line. Every case that renders a report carries it.
- `issues`: the count line and the risk line (both in the plugin's own words when it has them), the why line, the check line (both plugins omit it from 0.6.0). Every case that expects at least one issue carries it.

To add a free plugin, list it under `plugins` in `pack.json`. Then end each case's `graders:` list with:

```yaml
  # >>> free-plugin-standard: always issues
  # <<< free-plugin-standard
```

Then run `python3 free-plugin-standard/sync_graders.py`. A case that renders no report is listed under the plugin's `exempt` with a reason.

CI runs `sync_graders.py --check`, which fails when a block is missing or stale. CI also runs a never-worse-than-main test: it scores every case's graders, as on main and as on the branch, against saved real reports in `corpus/`. It fails if the branch passes a check main fails, or fails a report main passes, unless that exact check on that report is listed in `ALLOWED` (as a new alarm or as a looser check) with the reason main was wrong. Once the pull request merges and main fails the report the same way, the entry is used up and main stays green; an entry fails the test only when the branch no longer needs it. A release that adds a check, or rewords a fixed line, lists it in `NEW_GRADERS` once per case as (plugin, case, grader name) with the version that adds it and the reason. Saved reports in that case from older versions may fail exactly that check without counting as new alarms; newer reports count as usual for every other check, and an entry never excuses a looser check on an older report, or any other check. On reports at or after its version, a reworded check is not compared with main's old wording, so the test cannot catch a reword that also loosens the line: read reworded patterns by hand. The release adds its own eval reports to `corpus/` too: the test fails an entry unless at least one saved report at or after its version passes the check, at least one older report fails it, and it has a reason and a dotted version, and the case on the branch has a grader with that name. Add a plugin's saved reports to `corpus/` when you register it.

## Shared rules

custody-check and build-decisions use some rules together: the extra-risk field names and how a name matches, the files never to open, the "What a mistake costs" sentences, and the one safety line for a key ("assume it is exposed, and replace it now with a new one"). The one place to change them is `free-plugin-standard/shared/shared_rules.py`. Each plugin ships a byte-identical copy next to its scripts, and its markdown carries the generated text between `<!-- shared:NAME -->` and `<!-- /shared:NAME -->` markers. Never edit a copy or the text between markers by hand.

1. Have Python 3.9 or newer, `pip install pyyaml==6.0.2`, and a clone with its history (`git fetch origin main`): the differential tests read released main.
2. Edit `free-plugin-standard/shared/shared_rules.py`.
3. Run `python3 free-plugin-standard/sync_shared.py`. It rewrites both copies and every marked block, and writes nothing when any check fails.
4. Fast check: `python3 free-plugin-standard/sync_shared.py --check && python3 -m unittest discover -s free-plugin-standard -p '*_test.py'`.
5. Full check, as CI runs it: `CUSTODY_SLOW=1 CUSTODY_REQUIRE_GIT=1 python3 -m unittest discover -s custody-check/skills/custody-check/scripts -p '*_test.py'` and `CENSUS_SLOW=1 python3 -m unittest discover -s build-decisions/skills/build-decisions/scripts -p '*_test.py'`. A field-list change also moves each plugin's never-worse-than-main differential test: list any new alarm there with its reason.

Worked example, adding the field `tax_id`: append `"tax_id"` to `STOPLINE_FIELDS`. Before step 3, `--check` exits 1 with one line per file:

```
stale-copy build-decisions/skills/build-decisions/scripts/shared_rules.py:1 block shared_rules: run: python3 free-plugin-standard/sync_shared.py
stale-copy custody-check/skills/custody-check/scripts/shared_rules.py:1 block shared_rules: run: python3 free-plugin-standard/sync_shared.py
hand-edited build-decisions/skills/build-decisions/SKILL.md:25 block stopline-fields: run: python3 free-plugin-standard/sync_shared.py (edit free-plugin-standard/shared/shared_rules.py, not this block)
hand-edited custody-check/skills/custody-check/SKILL.md:24 block stopline-fields: run: python3 free-plugin-standard/sync_shared.py (edit free-plugin-standard/shared/shared_rules.py, not this block)
```

Step 3 prints `wrote <file>` for those four files, and `--check` then prints nothing and exits 0.

- **The CI guard.** `--check` also fails when a plugin's own `.py` file defines a shared name (`STOPLINE_FIELDS`, `stopline_terms`, the `NEVER_OPEN_*` names and the others in `GUARDED_NAMES`), or writes the key sentence out by hand in a `.py` file, `SKILL.md` or `assets/*.md`. Use the shared module, or add the path to `EXCLUDED` in `sync_shared.py` with a reason.
- **Never-open extras.** A plugin may add files it alone never opens, under its own `EXTRA_NEVER_OPEN_*` name, with the reason written in `SCOPE.md`. custody-check's MCP extras (`NEVER_OPEN_MCP_PATHS` and the others) are of this kind. There is no plugin-local extra for the field names.
- **Rebasing.** On a conflict in a copy or a marked block, resolve it in `shared/shared_rules.py` only, then rerun step 3. To roll back, roll back the canonical file and its copies together.
