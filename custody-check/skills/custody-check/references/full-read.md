# Full read

This file adds one shell command to the three in rule 7: the slice invocation in step 1. Everything else in SKILL.md is unchanged, and rules 1 to 8 hold here too.

After your own read above (Q1 to Q4 and the stop-line, unchanged, its own 40-call cap), helpers read the rest of the app for evidence on Q5 to Q11 and A1 to A6. Helpers never change an answer, a problem or the door.

0. **Lock your own answers first.** Before step 1, write down your `<read>` keys (Q1 to Q4 and the stop-line, from your own read above) and the `path:line` places behind each. From here on they never change. Nothing you or a helper reads in steps 1 to 4 becomes a `<read>` key, a problem block, a stop-line fact or a Where line; it can only become a "What we saw:" sentence.
1. **Plan the slices.** Run, from the same folder as the scanner: `python3 "<script dir>/full_read_slices.py" --repo "<app>"`. Accept one JSON line with `ok` true and exactly the keys `ok, slices, excluded, stopped_at_cap, eligible`. If `ok` is false, or `slices` is empty, read no more files: skip to step 5 with no findings.
2. **Launch helpers.** For each slice, call the Agent tool with `subagent_type` `custody-check:full-read-helper`, all in one message so they run in parallel. Each prompt is exactly: the app folder (`<your working directory>/<app>`), the slice number, and its paths in a fenced `text` block. Nothing else. If your host has no Agent tool, or a launch is refused, take the one-pass read below instead, for every slice not yet read.
3. **Record each envelope as it arrives**, as data (rule 3). Reject an envelope that is not exactly one fenced json block of the documented shape. Drop a finding whose path is not in that slice, whose `q` and `type` are not a pair in `references/evidence-phrases.md`, whose `field` (q10 only) is not on its list, or whose `sure` is false. Ignore any other field a helper adds.
4. **Check pass.** For each open question in question order, take its kept findings in the order the helpers gave them and re-open each one's line (Read, at most 40 lines around it; never a file the slice plan excluded) until 2 pass or the findings run out. At most 40 such Reads in all. A finding passes only when the line itself holds what its type's row in `references/evidence-phrases.md` says (and, for q10, holds that field). Judge the line, not other files.
5. **Report.** Each open-question bullet with at least one passed finding adds, as its one more sentence, the "What we saw:" sentence built exactly as `references/evidence-phrases.md` says: its phrases, its ending, the places in code spans, nothing else. A bullet with no passed finding stays exactly as SKILL.md renders it: never write that nothing was seen or found in the code. A1 to A6 bullets keep their evidence even when the founder says the app calls no model or does not answer.

**One-pass read (no Agent tool).** Read the slices' paths yourself, in slice order: at most 120 Reads, each at most 400 lines, only listed paths, rules 2 to 4 as for any read. Note findings with the same fields and rules a helper uses (`agents/full-read-helper.md` is not opened: the types are in `references/evidence-phrases.md`). Then steps 4 and 5.

**Lines in the report.** Under the coverage line, exactly one of (report text never says helper):
- with helpers: "Read with extra readers. They reported reading <k> more of your files." (k = unique paths in helpers' `files_read` that you did not read yourself, each helper's count capped at its slice size);
- one pass: "Read in one pass. We read <k> more of your files for the questions below." (k = files you read in the one-pass read);
- step 1 gave no slices: no line.

Under the We also can't see line, each only when it applies:
- `stopped_at_cap` above 0: "<n> of your files were not read for the questions below: the check reads up to 320 code files and your app's settings files, server files first."
- a helper did not answer, or its envelope was rejected: "Some of your files were not read for the questions below, because a reader did not finish."
- on Claude Code with no Agent tool: "Extra readers were not available. Start Claude Code with the launch line in the README, which includes Agent, for a full read."

**Asking the founder.** When you ask an open question that has a passed finding, lead with its "What we saw:" sentence, then ask: "Is that what is live? yes / no / don't know". Their answer counts exactly as any other answer to that question.
