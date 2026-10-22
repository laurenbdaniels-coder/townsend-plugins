# The free-plugin report standard

What each free plugin does and doesn't do is decided in `SCOPE.md`; this file is the report shape. When the two disagree, SCOPE.md wins.

Every free Townsend plugin that checks an app reports to this standard (spell-it-out, which only changes how Claude asks questions, is outside it). Reference implementation: build-decisions 0.4.0 (decision-census 0.3.1 and later before the rename), `build-decisions/skills/build-decisions/SKILL.md` Step 5.

## The reader

The reader built their app by prompting an AI tool. They are an ordinary adult who does not read or write code. They know the app by its screens, buttons, plans and prices. Every sentence must make sense to them without a programmer next to them.

## The no-fix line

A free plugin **diagnoses and verifies**. It finds the issue, says what goes wrong, and gives a check the reader can run in a minute. custody-check 0.6.0 and later stops at the diagnosis: its report says what is broken and what it means for the reader, and gives no check (Lauren, 2026-10-21).

It never gives fix steps, code, a prompt that changes the app, or an offer to make changes, now or in another conversation. That holds even when the reader asks for a fix. Every prompt it gives for the reader's AI tool ends "Change nothing."

A generic fix prompt is unsafe: an AI tool can drop the server's copy of an access rule.

## The report, in order

1. **Title.** Nothing comes before it.
2. **The count**, one bold line: `**Your app has N <issues> ...**`. When nothing is found, one plain line says so ("This run found no ..."). custody-check words it `**We found N problems in your code, and M things your code can't tell us.**`, with "no" for zero.
3. **Why this matters:** one fixed line, the risk in everyday terms (what breaks, what the user sees).
4. **Each issue** (at most 4, then "And N more"):
   - a numbered bold title in plain words, with how many places;
   - each place as one plain sentence about what it does in the app, then `path:line` at the end;
   - the plugin's risk line: what the reader would see go wrong. build-decisions says `If they get out of sync:`; custody-check says `What it means for you:`;
   - `Check it (1 min):` short steps in the running app, or a plain question for their AI tool ending "Change nothing." custody-check leaves it out.
5. **Before you change any of these:** ask your AI tool "... Change nothing.", then the Free Assessment link. When the stop-line is ticked, there is no link: tell the reader to get a person who does this for a living first. custody-check leaves out this line and the link.
6. **Also worth a look:** at most 2 short lines, or nothing.
7. **Not checked:** one fixed line that names what the run did not look at and ends "Not found does not mean it isn't there." A free plugin never says the app is clean.
8. **Pointer** to the other free plugin: build-decisions points to custody-check (keys, data access and who can call what). custody-check has no pointer.
9. **Footer:** plugin name and version, what was read, "read-only", "a review, not an audit".

The per-issue lines use these exact words, with two kinds of exception in `pack.json`. A plugin may give its own `words` for a grader listed in `plugin_words`: the risk line, as a plain label ending in a colon ("out of sync" fits copies of a rule and not an open key), and the count line, as one bold line that starts with a word. A plugin may `omit`, with a reason, a grader listed in `omittable` (only Check it). The no-fix line (no fix prompt, no code words) can never be reworded or left out. `sync_graders.py` checks each shape. A plugin whose issues need other words changes this standard, and the shared graders, in a pull request. It does not loosen its own graders.

custody-check 0.6.0 and later has its own plain shape: count, why, a coverage line, an extra-risk block when its stop-line is ticked, a Do today line when a key was seen, the issue blocks under "What we found in your code" (bold title, What it means for you, Where), the open questions under "What your code can't tell us", a not-checked line, the footer. The door, the eleven, the tier and the five stay in the workshop and its README, not in the report.

## Plain English

- ASD-STE100 Simplified Technical English. One idea per sentence. Active voice, present tense, common words.
- At most 25 words in a sentence, at most 20 in an instruction.
- No programming words outside file paths: function, helper, constant, variable, import, endpoint, API, route, component, middleware, schema, migration, query, SQL, console, terminal, boolean, enum, string, array, null, config, regex, props, backend, frontend, codebase, hard-coded, allow-list, refactor.
- Describe each place by what a person using the app would notice, never by how the code does it.
- Analysis, not inventory: no lists of every place found, no explanation of places that are fine.

## Evals

`claude plugin eval` has no include for `case.yaml`, so the shared graders live in `pack.json` and are copied into each case:

- `always`: no fix prompt, no code words. Every case that renders a report carries it.
- `issues`: the count line and the risk line (both in the plugin's own words when it has them), the why line, the check-it line (unless the plugin omits it). Every case that expects at least one issue carries it.

To add a free plugin, list it under `plugins` in `pack.json`. Then end each case's `graders:` list with:

```yaml
  # >>> free-plugin-standard: always issues
  # <<< free-plugin-standard
```

Then run `python3 free-plugin-standard/sync_graders.py`. A case that renders no report is listed under the plugin's `exempt` with a reason.

CI runs `sync_graders.py --check`, which fails when a block is missing or stale. CI also runs a never-worse-than-main test: it scores every case's graders, as on main and as on the branch, against saved real reports in `corpus/`. It fails if the branch passes a check main fails, or fails a report main passes, unless that exact check on that report is listed in `ALLOWED` (as a new alarm or as a looser check) with the reason main was wrong. Once the pull request merges and main fails the report the same way, the entry is used up and main stays green; an entry fails the test only when the branch no longer needs it. A release that adds a check, or rewords a fixed line, lists it in `NEW_GRADERS` once per case as (plugin, case, grader name) with the version that adds it and the reason. Saved reports in that case from older versions may fail exactly that check without counting as new alarms; newer reports count as usual for every other check, and an entry never excuses a looser check on an older report, or any other check. On reports at or after its version, a reworded check is not compared with main's old wording, so the test cannot catch a reword that also loosens the line: read reworded patterns by hand. The release adds its own eval reports to `corpus/` too: the test fails an entry unless at least one saved report at or after its version passes the check, at least one older report fails it, and it has a reason and a dotted version, and the case on the branch has a grader with that name. Add a plugin's saved reports to `corpus/` when you register it.
