# The free-plugin report standard

Every free Townsend plugin that checks an app reports to this standard (spell-it-out, which only changes how Claude asks questions, is outside it). Reference implementation: build-decisions 0.4.0 (decision-census 0.3.1 and later before the rename), `build-decisions/skills/build-decisions/SKILL.md` Step 5.

## The reader

The reader built their app by prompting an AI tool. They are an ordinary adult who does not read or write code. They know the app by its screens, buttons, plans and prices. Every sentence must make sense to them without a programmer next to them.

## The free/paid line

A free plugin **diagnoses and verifies**. It finds the issue, says what goes wrong, and gives a check the reader can run in a minute.

It never gives fix steps, code, a prompt that changes the app, or an offer to make changes, now or in another conversation. That holds even when the reader asks for a fix. Every prompt it gives for the reader's AI tool ends "Change nothing."

Choosing the fix and making it safely is the paid work. A generic fix prompt both gives that judgment away and is unsafe: an AI tool can drop the server's copy of an access rule.

## The report, in order

1. **Title.** Nothing comes before it.
2. **The count**, one bold line: `**Your app has N <issues> ...**`. When nothing is found, one plain line says so ("This run found no ...").
3. **Why this matters:** one fixed line, the risk in everyday terms (what breaks, what the user sees).
4. **Each issue** (at most 4, then "And N more"):
   - a numbered bold title in plain words, with how many places;
   - each place as one plain sentence about what it does in the app, then `path:line` at the end;
   - the plugin's risk line: what the reader would see go wrong. build-decisions says `If they get out of sync:`; custody-check says `What could go wrong:`;
   - `Check it (1 min):` short steps in the running app, or a plain question for their AI tool ending "Change nothing."
5. **Before you change any of these:** ask your AI tool "... Change nothing.", then the Free Assessment link. When the stop-line is ticked, there is no link: tell the reader to get a person who does this for a living first.
6. **Also worth a look:** at most 2 short lines, or nothing.
7. **Not checked:** one fixed line that names what the run did not look at and ends "Not found does not mean it isn't there." A free plugin never says the app is clean.
8. **Pointer** to the other free plugin: build-decisions points to custody-check (keys, data access and who can call what); custody-check points to build-decisions (a rule decided in more than one place).
9. **Footer:** plugin name and version, what was read, "read-only", "a review, not an audit".

The per-issue lines use these exact words. The risk line is the one exception: each plugin names its own in `pack.json` (`words`), because "out of sync" fits copies of a rule and not an open key. Only the graders listed in `plugin_words` can be reworded, and only to a plain label ending in a colon. A plugin whose issues need other words changes this standard, and the shared graders, in a pull request. It does not loosen its own graders.

custody-check keeps its verdict's own shape around these parts (the door, the eleven, the tier and the five, which the workshop handout uses): its Patch list items are the issue blocks, and the Free Assessment line closes its "Before you change any of these" line.

## Plain English

- ASD-STE100 Simplified Technical English. One idea per sentence. Active voice, present tense, common words.
- At most 25 words in a sentence, at most 20 in an instruction.
- No programming words outside file paths: function, helper, constant, variable, import, endpoint, API, route, component, middleware, schema, migration, query, SQL, console, terminal, boolean, enum, string, array, null, config, regex, props, backend, frontend, codebase, hard-coded, allow-list, refactor.
- Describe each place by what a person using the app would notice, never by how the code does it.
- Analysis, not inventory: no lists of every place found, no explanation of places that are fine.

## Evals

`claude plugin eval` has no include for `case.yaml`, so the shared graders live in `pack.json` and are copied into each case:

- `always`: no fix prompt, no code words. Every case that renders a report carries it.
- `issues`: the count line, the why line, the risk line (`std-out-of-sync`, in the plugin's own words), the check-it line. Every case that expects at least one issue carries it.

To add a free plugin, list it under `plugins` in `pack.json`. Then end each case's `graders:` list with:

```yaml
  # >>> free-plugin-standard: always issues
  # <<< free-plugin-standard
```

Then run `python3 free-plugin-standard/sync_graders.py`. A case that renders no report is listed under the plugin's `exempt` with a reason.

CI runs `sync_graders.py --check`, which fails when a block is missing or stale. CI also runs a never-worse-than-main test: it scores every case's graders, as on main and as on the branch, against saved real reports in `corpus/`. It fails if the branch passes a check main fails, or fails a report main passes, unless that exact check on that report is listed in `ALLOWED` (as a new alarm or as a looser check) with the reason main was wrong. Once the pull request merges and main fails the report the same way, the entry is used up and main stays green; an entry fails the test only when the branch no longer needs it. A release that adds a check, or rewords a fixed line, lists it once in `NEW_GRADERS` as (plugin, grader name) with the version that adds it and the reason: saved reports from older versions may fail that check without counting as new alarms, and newer ones count as usual. A `NEW_GRADERS` entry never excuses a looser check, and it fails the test when no older report fails its check or its grader is gone. Add a plugin's saved reports to `corpus/` when you register it.
