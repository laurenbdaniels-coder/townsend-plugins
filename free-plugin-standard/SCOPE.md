# What the two free plugins do and don't do

The one place this is written down. Every plan, template, SKILL.md, README, deck slide and site line about
custody-check or build-decisions agrees with it. A change starts here, with the date and who decided, before any
other file moves. `scope_test.py` checks the parts a machine can check.

Decided by Lauren Townsend. Last change: 2026-10-23.

## What these plugins are

They find issues. They do not fix anything, and they do not suggest fixes. Fixing is a different tool, built
separately; these plugins neither do it nor point to it. (Lauren, 2026-10-21)

## Both plugins

They do:
- Read the app's files. They never change anything in the app.
- Say what is broken and what it means for the founder. (2026-10-21)
- Say what the code can't tell, as open questions. An open question is not a failure.
- Write for a founder who built the app with an AI tool and does not read code: plain English, short sentences,
  no programming words outside file paths.

They don't:
- Fix anything, or suggest a fix: no fix steps, no code, no prompt that changes the app, no offer to fix, no
  "what to do next", even when the founder asks. One exception, for safety: a key that may be exposed gets
  "replace it now". (2026-10-15, 2026-10-21)
- Recommend anything: no "ship it", "patch it", "get a person", "you should". Not in the report, and not in any
  copy about the plugins (README, site, deck, taglines). (2026-10-21)
- Mention any other service, offer or price, or link to one, in the report or the skill files. The README may
  carry the Free Assessment link. (2026-10-21)
- Point to the other plugin in the report. (2026-10-21)
- Repeat a key, or send anything anywhere from their own scripts.

## What they ask the founder

- Never ask what the code should show. Use what was found; what it could not settle becomes an open question in
  the report. (2026-10-21)
- Ask only what code can't show, one question at a time. "Don't know" is a fine answer and is never argued with.
- Each question may carry a one-minute test the founder can run to find the answer, in the chat only, never in
  the report. (2026-10-21)
- The founder may paste their answers up front instead.

## Custody Check

Shows what a stranger could see or do in your app, and what your code can't tell it.

Never asks about: keys, what runs in the browser or on the server, who can read data, who can change data, or
whether one place decides who is allowed. (2026-10-21)

Asks about, only when the code doesn't already show it: the stop-line (the app handles card details itself, holds
or moves other people's money, keeps health data or other people's sensitive data, or runs at real scale or under
a contract that needs it up). (2026-10-21)

Asks about, when still open: backups, reading changes before they go live, what one user costs, alerts when it
breaks, what personal data the app keeps and why, exporting code and data, and whether the app calls an AI model
(then the six AI questions). When the scan could not run, it also asks whether the code can be got back and
whether there is a copy that isn't live. (2026-10-21)

The report, in order: the count ("We found N problems in your code, and M things your code can't tell us."), why
it matters, how much code it read, the extra-risk block when the stop-line is ticked (a plain fact, never advice),
"Do today: replace N secret keys" when a key was seen, each problem (title, "What it means for you:", "Where:"),
the open questions, what it can't see (with the rerun line when the scan stopped early), the footer. Nothing after
the footer.

Never in the report: the door, the eleven table, the tier, the five, question numbers, "Check it", a question for
the founder's AI tool, "Before you change any of these". (2026-10-21) The eleven questions and the five stay in the
README's "From the workshop".

## Build Decisions

Shows where your app decides who sees what and what things cost, and which rules it wrote more than once.

From 0.6.0 the same rules apply as for Custody Check: what is broken and what it means, nothing to do, no link, no
pointer, and questions only about what code can't show. (2026-10-21) Until 0.6.0 ships, 0.5.x still prints
"Check it", "Before you change any of these", a link and a pointer.

It also shows values your screens choose that your server saves or counts without checking. (Lauren, 2026-10-21; recorded 2026-10-22) It never says what to change. Screens that promise something no code was found for are not
reported: the 2026-10-22 sample found too many false alarms (Lauren, 2026-10-22).

Warnings (Lauren, 2026-10-23; not built yet). Build Decisions may also show three kinds of warning: one job done
several ways, code that never runs, and more parts than the app uses. A warning is not a problem. It is not
counted in the opening count line, which stays the same. Warnings get their own section after the problems, headed
with their own number. Each warning says what it means for the founder and never says what to change. Each kind
ships only after its own false-alarm sample passes the same bar as the other checks: at least half of what it
flags is real, and it flags at most 1 in 10 apps that are fine. A kind that fails is cut.
