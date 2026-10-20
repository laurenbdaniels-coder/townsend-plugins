# Changelog

The footer of every report names the version that produced it. Up to 0.3.2 this plugin was called decision-census.

## 0.6.0 (2026-10-19)

- **Back: whether payment messages are checked.** A payment handler with no sign of a check that its messages really come from the payment company is an "Also worth a look" line again, ending "Custody Check answers whether a stranger can use this." The "Not checked" line no longer says this is not checked.
- **Rebuilt so it does not cry wolf.** Imports are followed the way the app's own `tsconfig.json` / `jsconfig.json` says (`paths`, `baseUrl`, local `extends`; comments and trailing commas are fine), and every name is tried as a code file first (`./webhook.utils`, `../lib/stripe.edge`); only stylesheets, images and data files count as non-code. The old guesses (`@/` means the root or `src/`) are gone.
- **When unsure, it says nothing.** "No check found" needs a sure chain: every import placed on exactly one file this run read. Two possible files, an alias with no settings, settings from an installed package, a config that does not parse, a path in backticks, a comment mark after code that may be a regex (`/[/*]/`), a check in a file that imports the handler (it may guard another route), and the time limit all make the verdict "not determined", which the report never prints.
- **Also not determined:** a handler that hands the signature to a package or helper this run does not judge (a sync engine that checks it), and a handler some file may mount through an import this run cannot place (an alias from `module-alias`, a `#` subpath).
- **Also counted as a check:** a hand-made HMAC compared with a value read from the request headers, whatever its names (`digest !== header`), or both passed to a compare call. An HMAC used as a dedup key or a lookup is not a check. Python `from pkg import a, b` follows every module named.
- **Monorepos:** a tsconfig that extends the repo's own config package (`@repo/typescript-config/nextjs.json`) is followed.
- **Every case from the 0.5.0 review** is a labeled fixture with a main-vs-branch reason; CI fails if a listed exception would ever let a new "no check found" through. The 42 saved 0.5.0 eval reports join the shared corpus.

## 0.5.0 (2026-10-19)

- **Where your app saves whether someone has paid.** A third helper call, `census_scan.py --section payment`, lists places that save paid status, a plan or credits; Stripe payment handlers; a price written in the app beside a Stripe price id; and screens that save credits, a plan or an order total straight to the database. The agent reads each place before it reports it.
- **In the report.** Paid status saved in two or more places is a numbered rule, "Whether someone has paid", with a check (open the thank-you page without paying, when one saves paid status). A price in the app that the payment company also charges is a rule with a compare-the-checkout check. A screen that seems to save money or paid fields itself is an "Also worth a look" line ending "Custody Check answers whether a stranger can use this."
- **Held back: whether payment messages are checked.** The helper still looks for a Stripe signature check, but the report prints nothing about it. Review found it said "no check found" on apps that do check (a dotted file name, two `lib` folders behind `@/`, a regex that looks like a comment). The "Not checked" line now says so. A rebuilt check is the next release.
- **One line on the boundary,** in both plugins' README and description: "Build Decisions shows where your app decides each thing and in how many places. Custody Check answers what a stranger can do and which door your next change takes." It matches custody-check 0.5.0's "one place decides" pointer.
- **Stop-line follows custody-check.** Card details held by the app itself, money held or moved for other people, health or other sensitive data, real scale or an uptime contract tick it. Checkout, subscriptions, invoices and refunds the payment company runs do not, and neither do the payment findings.
- **"Not checked"** now names sign-in checks on server code and library versions, and says payment places are found from the files, not tested in the app.
- **Unchanged:** the census line and the architecture line are byte for byte the same as 0.4.0's (CI compares both with the release). The payment section has its own labeled app and a main-vs-branch test that turns on once 0.5.0 is released.
- **Evals:** two new cases (a paywall app with two paid writers, an unchecked handler and screen writes; an app whose handlers do check), hostile-repo text aimed at the payment section, and every case now allows three helper calls and checks the new "Not checked" line.

## 0.4.0 (2026-10-16)

- **Renamed: Build Decisions.** The plugin id is now `build-decisions`; say "run build decisions on ./my-app". `decision-census` 0.3.3 stays in the marketplace as a pointer that prints how to switch and runs nothing. Existing installs need the three commands in the README.
- **How your app is built.** The report adds one or two plain sentences after "Why this matters": whether the app's screens read and save data straight to the database, whether it runs some of its own code on a server, and whether there are signs of a second app that uses the same data. Then one sentence on the risk, never a fix. With nothing found, it says it could not tell. A rule found inside the second app says so in its place line.
- **A second helper call,** `census_scan.py --section architecture`, with its own walk, limits and failure line. The census call and its output are unchanged; CI checks that line byte for byte against the released one.
- **"Not checked" names what this version does not check yet:** payments, screens that write prices or paid status, sign-in checks on server code, and library versions.
- **Careful about what it claims.** "Screens read and save data straight to the database" needs a real database read or write in code that runs in the browser: type imports, sign-in calls and set-up don't count, and neither do loaders and server files in Next.js, Nuxt, Remix, React Router 7, Astro or SvelteKit (`.svelte` and `.vue` components and `'use client'` files do). Test, fixture and example folders are never apps, and an `ios/` or `android/` folder needs a real Xcode or Gradle project file. A second app needs a link another app can't explain away. App text is never turned into a pattern, and the section has its own limits on apps and time, so a hostile repo can't make it hang. Found in review on the pinned real-run app and on common monorepo layouts.
- **The old phrases.** With only the `decision-census` pointer installed, "run decision census" prints how to switch. The other old phrases ("where does my app decide", "a fix didn't stick") start Build Decisions once it is installed.
- **Evals:** two new cases (a web app with a linked phone app; an app with no sign of how it is built), and three checks on every report case: the "How your app is built" line, no internal id, and the new "Not checked" line. The free-plugin standard's never-worse test now reads main's cases from the old folder name while the rename is in flight.

## 0.3.2 (2026-10-16)

- **The report standard is shared.** The shape this census reports in (the count, why it matters, each rule with what goes wrong and a one-minute check, then "Before you change any of these") is now the standard every free plugin follows: `free-plugin-standard/STANDARD.md`. The census report does not change.
- **Evals:** six checks now come from the shared pack (`free-plugin-standard/pack.json`), stamped into each case by `sync_graders.py`. The four census checks the pack repeats were removed, so each case holds one copy. The clean-looking and stop-line cases now also check for fix prompts and code words, and the "fix it too" case checks the full report shape. On the saved reports, every 0.3.1 report passes the shared checks; the new alarms are all on older releases.
- **Credits:** the ASD-STE100 line no longer credits another skill. No text was copied from it.

## 0.3.1 (2026-10-15)

- **Diagnose, never prescribe.** The "To fix" line is gone. In its place: "Before you change any of these", with one question for your AI tool that ends "Change nothing.", and the Free Assessment link (no link when the stop-line is ticked). A new rule says the census never gives fix steps, code, a prompt that changes the app, or an offer to make changes, even when you ask it to fix things. Choosing the real copy and changing the others safely needs judgment; a generic "put it in one place" prompt could make an AI tool drop the server's copy of an access rule.
- **Evals:** checks for the new line, against fix prompts and offers to fix, and against unfilled `<…>` placeholders, on every case with planted pairs and on the "fix it too" case. The new-line and no-fix-prompt checks failed on the saved 0.3.0 reports.

## 0.3.0 (2026-10-15)

- **A report that says what is at risk.** It opens with how many rules your app writes in more than one place, then one fixed line on why that matters: a change can land in one copy and miss the others, and the app then does things you don't expect. Each rule follows with how many places hold it, each place as a plain sentence with its file at the end, what you would see if the copies get out of sync, and a one-minute check. A "To fix" line gives a prompt for your AI tool. The "Screen:/Server:" labels are gone, and nothing comes before the title.
- **Evals:** the planted-pair checks now match any bullet that names the file, and new checks require the count line, the "why this matters" line, an "if they get out of sync" line and the "To fix" line on every case with planted pairs. All four new checks failed on every saved 0.2.1 report.

## 0.2.1 (2026-10-15)

- **Written for founders who don't code.** The report now speaks to an ordinary adult who built the app with an AI tool and does not read code. Each place is described by what it does in the app ("hides the Suspend button for the owner"), not by how the code does it. Programming words (function, helper, constant, endpoint, schema, query and the like) are not used outside file paths. Every check is done in the running app, or is a plain question to ask your AI tool, never a database console.
- **Evals:** a new check on the seeded, crowded, clean-looking, shared-constant and shared-helper cases fails a report that uses programming words outside file paths. It failed 1 of 3 shared-helper runs on 0.2.0.

## 0.2.0 (2026-10-15)

- **A short analysis, not an inventory.** The report is now a few lines: how many decisions are made in two places, one block per decision (the two places, a one-minute check), at most two "worth a look" lines, what was not checked, and the next step. The per-place lists and long fixed sections are gone. A typical report is under 30 lines.
- **It searches your code.** Starting from the helper's places, the agent searches and reads the app (read-only, at most 120 lines at a time, at most 40 searches and reads) to see where each rule or value is defined and whether two places share one source. It used to read only 31 lines around each place. Instruction files, `.env` files, lockfiles and build folders are still never opened.
- **Cards mean own copies.** A decision is reported when two places each hold their own copy of the rule or value, whether or not they differ today; the check finds out.
- **Evals** retargeted to the new report: a length limit, no long sections, the "not checked" line, and safety checks for the wider reading (never open instruction or `.env` files, at most one shell command, at most 40 reads and 40 searches, every read limited to 120 lines, every search file-names-only with the code-file list, and every read and search inside the app with no `..`). The planted-pair checks look only at card lines. Two fixtures were made unambiguous.

## 0.1.2 (2026-10-15)

- **Plain English.** The census is written in ASD-STE100 Simplified Technical English, applied the way Matt Pocock's `/wait-what` skill (MIT) does: a short line of context first, one idea per sentence, at most 25 words a sentence (20 for an instruction), active voice, and the same small set of words every time (place, decision, card, one source, found, read). Long lists became bulleted lists. Checks by hand are short steps.
- **Fixed text rewritten to the same rules:** what the census can't tell you, the stop-line question and footer, and the one prompt.
- **Evals:** two new graders on the seeded, crowded and clean-looking cases. No sentence may run over 25 words, and the context line must come first.

## 0.1.1 (2026-10-15)

- **Fewer false cards.** Two places that read the same shared list, constant or helper (defined once and imported) are one source, not two answers: the census lists them with a one-line note and makes no card. Found on a real app, where two of three cards were pairs like this. A new eval case, `shared-constant-app`, holds it: one shared list that must not be carded beside a real duplicated price that must be. A second case, `shared-helper-diverges`, checks the other side: two places that import one shared price or helper and each add their own discount or filter are still carded.
- **Wording.** Notes about the places read say what they are ("counts and layout, not prices") instead of "none".

## 0.1.0 (2026-10-15)

First release.

- **Census.** It lists every place this run finds where an app decides who can see a record, what something costs, whether someone has paid, and how money rounds. Each decision found in more than one place gets a two-answer card with a check you can run by hand. The census never says the app is clean.
- **Helper.** `census_scan.py` walks the app with custody-check's walk rules and never-open list. It prints one JSON line with paths, line numbers and fixed pattern names only, never text from inside a file. File names with unusual characters are held back and counted.
- **Bounded reading.** The agent reads up to 24 windows of 31 lines around listed places, and nothing else in the app.
- **Stop-line.** Sensitive field names in schema files (`card_number`, `date_of_birth` and the like), or the founder's answer, make the census say **Get a person**, with no booking link.
- **Tests.** Unit tests, a never-miss and noise test that compares every later version with the released one, and eight `claude plugin eval` cases run three times each before release.
