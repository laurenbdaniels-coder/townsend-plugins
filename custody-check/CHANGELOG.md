# Changelog

The footer of every verdict names the version that produced it. Later entries carry a "What changed since the workshop" line so an attendee can tell whether an answer would come out differently today.

## 0.3.0 (2026-09-23)

What changed since the workshop build: "looked hard and found nothing" now reads differently from "did not look", and a folder of photos no longer makes the scan count as incomplete.

- **Added.** A fourth answer, **Nothing found** (`nothing-found`), for Q1, Q3 and Q9. It means the scanner read the files that could hold the answer, ran every check, and came back empty, and the row says what it read ("214 files read: no key in client code, no MCP token, no tracked env file"). It is only claimed on a complete scan, never for a question the scanner had nothing to read for (Q3 with no SQL or rules file stays Don't know), and it is never a yes: for the door it counts as Don't know, so no door changes. It stays on the Don't-know list with its by-hand test, because a file tree cannot see the running app.
- **Earned, not assumed.** "Nothing found" is withheld whenever the scanner skipped something that could hold the answer: a large or binary-looking code, config or rules file, an unreadable or linked file or folder, a minified bundle or source map, a folder you excluded, a key-shaped value too long to judge, a skipped dependency manifest, or evidence trimmed to fit the output. Q3 also withholds it when a migration creates a public table and no migration turns row level security on for it (new evidence row `table-without-rls`), which is the most common open table on Supabase. Also withheld, found in the pre-merge review: a migration with more tables than the scanner reads per file, a `requirements.txt` that includes another file, a `build`, `dist` or `out` folder (for Q3 and Q9 as well as Q1), a precompressed bundle (`app.js.gz`), and any file the walk saw but could not open, which now counts as an error and makes the scan partial instead of hiding among links and special files.
- **Fixed.** Env files named `.env-production`, `.env_prod` or in capitals (`PROD.ENV`) were not recognised, so a committed one was missed; they are now, and `.env_example`-style templates stay templates. Q9's "N dependencies read" now counts only entries a manifest parser actually read (`package.json` sections, `requirements.txt` lines, PEP 621 lists, Poetry dependency tables, `gem` lines, `go.mod` requires); TOML keys, classifiers, keywords and `-r` includes are not dependencies; an include, an editable install, a VCS or URL requirement, and a `package.json` that does not parse are gaps. Ruby and Go error-tracking packages (`sentry-ruby`, `honeybadger`, `sentry-go`, and others) are now recognised, so those apps can reach a monitoring hint at all.
- **Build folders.** A `build`, `dist` or `out` folder is still not read, but it now keeps Q1, Q3 and Q9 off Nothing found, with one `build-output-unread` row listing the folders; `.next`, `.nuxt` and a `vendor` folder below the root count too. Found by running the check on a real prototype whose whole source lived in `build/`: it had reported "nothing found" after reading one file.
- **Added.** Evidence the scanner already had and did not show: Q2 now says how many code files it classified as browser, server or unclear; Q6 notes that a `vercel.json` or `netlify.toml` means preview deployments exist by default; Q7 sees a review bot on pull requests (a workflow named `preview.yml` is not counted as one); Q11 says the code and its git history are on this machine. None of these changes an answer. They turn a bare "don't know" into one with something to look at.
- **Fixed.** A large file only makes the scan partial when it is a kind that could hold a key or an access rule (code, HTML, JSON, YAML, TOML, SQL, rules, env). Before, one ordinary app with 99 large photos came back "scan incomplete" by default, and the verdict rule never lets an incomplete scan reach Ship it, so a healthy app was steered off the door for containing pictures. The footer still counts the skipped files, and a new stat, `files_skipped_oversize_relevant`, counts the ones that matter.

## 0.2.0 (2026-09-23)

What changed since the workshop build: if AI drives part of your product, the check now asks six more questions about keeping it on rails.

- **Added.** Six questions that apply only when the app calls a model: how slow is too slow and what happens past it; where your prompts live and which version produced an answer; whether production is running what you actually tested; whether a change made things better rather than just different, and whether you are judging on examples nobody tuned against; what a user sees when the model is wrong, refuses, or is down; and whether you would notice the model changing under you or your own product moving away from your examples.
- Three of them are the hand-operated versions of failures people who train models know as training and serving skew, overfitting the validation set, and stale labels. You get all three without training anything, because a model is a moving part inside your product. The training-shaped versions are named for the few founders who do train, each with its own test.
- Every question ends with a fix the founder can start in the room, and the tests are written to be run by the founder's own AI tool where it can do the work faster than they can.
- They are interview questions. The scanner does not answer them, the JSON contract is unchanged, and they never change the door: the door is still the eleven. What they change is the list of things you leave knowing you cannot yet answer.
- **Fixed.** Every wall-clock linearity bound in the test suite now scales with `CUSTODY_TIME_SLACK`, so a loaded machine cannot fail a test that is asserting linearity rather than speed. CI sets it to 3.

## 0.1.1 (2026-09-22)

What changed since the workshop build: a repository that sets `core.hooksPath` is no longer refused.

- **Fixed.** The git guard refused any repository setting `core.hooksPath`, which husky and many JavaScript projects do, and a refused repository loses every git fact: the commit count, the tag count, and the committed-secrets check behind question one. That key, and four others, are already blanked on every git command this tool runs, so a repository setting them cannot reach us. The guard now holds only the directives a command-line override cannot neutralise.

## 0.1.0 (2026-09-17)

First release, the Seattle AI Week giveaway.

- The eleven custody questions as a runnable, read-only skill for Claude Code and Codex.
- A python 3.9 stdlib scanner that answers Q1 (secrets in the browser), Q3 (open tables and rules), the code half of Q5 (a previous version and a deploy path exist), and Q6 (named environments), and gathers evidence for the rest. Every output string is redacted; the scanner never opens instruction files (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.claude/`, `.codex/`, `.cursor/rules/`, and their relatives).
- A verdict with the tier of the next change, the stop-line, the door, a Patch list of at most three items, the five-if-only-five list, and a Don't-know list with a sixty-second by-hand test for each.
