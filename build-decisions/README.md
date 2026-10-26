# build-decisions

Build Decisions (until 0.3.2 called Decision Census; that name now installs a pointer to this plugin) is the companion to custody-check. custody-check covers "it says it's fine, and it's broken". This covers "it works, and it's piling up": the same decision made in two places, so a fix lands in one and the other stays broken, or one screen shows a price and checkout charges another. Both copies work today, which is why you can't see it from the app.

Build Decisions shows where your app decides the same thing twice. Custody Check shows what a stranger could see or do in your app, and what your code can't tell it.

It looks for the places where your AI-built app decides four things:

- **who can see a record**
- **what something costs**
- **whether someone has paid**
- **how money rounds**

It also finds **values the browser chooses**: a number, date, plan or role the screen sends that your server saves or counts by without checking it against its own record (for example points or credits a person can set for themselves). It reads up to 10 of your server files whole for this.

It also says, in one or two plain sentences, **how your app is built**: whether its screens read and save data straight to the database, whether it runs some of its own code on a server, and whether there are signs of a second app (a phone app, a second website) that uses the same data. A rule written into both apps can give two answers.

And it says **where your app saves whether someone has paid**: when two places do it (say, the payment company's message and a thank-you page), that is a rule written in more than one place. It points out a price written in your app that the payment company also charges, and a screen that seems to save credits, a plan or a total straight to the database.

You get a short, plain-English report, written for someone who builds with an AI tool and does not read code. It starts with how many rules your app writes in more than one place, and why that matters: when a change lands in one copy and misses the others, the app does things you don't expect. Then it says how much of your code it read, and for each rule the places as `path:line` with what each does in the app, and what it means for you. It says what is broken and what it means; it does not tell you what to do. Places that read one shared value are fine and are not reported.

An example (a made-up app):

```
# Build decisions: my-app

**Your app has 2 rules that are written in more than one place, and 1 value the browser chooses.**

Why this matters: when you or your AI tool change one of these rules, the change may land in one place and miss the others. Then the copies stop agreeing, and your app does things you don't expect. A button shows but fails, two screens show different prices, or something breaks.
When the browser chooses a value, a person using your app can change it before your server saves it.
We read 9 of your 41 code files. Problems in the others can be missed.

**How your app is built:** This run found that your app runs some of its own code on a server. It saw this in `app/api/checkout/route.ts`.

**1. The monthly plan price** (written in 2 places)
These places give different answers today.
- Shows $15 a month on the pricing page. `app/pricing/page.tsx:22`
- Charges $19 a month at checkout. `app/api/checkout/route.ts:41`

What it means for you: your pricing page shows one price, and checkout charges another.

**2. Who can see a project** (written in 2 places)
- Hides other teams' projects on the dashboard. `app/dashboard/page.tsx:58`
- Lets any signed-in person open a project by its address. `app/projects/[id]/page.tsx:12`

What it means for you: a person can open a project that the dashboard hides from them.

**3. Bonus credits: the browser chooses it.**
What it means for you: a person can give themselves any number of credits.
- Takes the number of credits from the screen. `app/api/bonus/route.ts:5`
- Adds that number to the person's account. `app/api/bonus/route.ts:6`

Also worth a look:
- A screen seems to save credits straight to the database (`components/Buy.tsx:30`). If it does, a person using the app could change it.

Not checked: database settings, dashboards, other projects, names this run does not know, and code it did not search. This version also does not check sign-in checks on server code, or library versions. Payment places are found from the files, not tested in the app. This version does not check whether payment messages really come from your payment company. It checks values the browser chooses only in your app's own server code, not in code that runs inside your database service. Not found does not mean it isn't there.

---
build-decisions v0.6.3 · read-only · a review, not an audit
```

It's a review, not an audit. It reports, and it changes nothing in your app. It never says your app is clean. "Not found" means not found by this run, never "not there".

## Step 0: get your code onto your machine

Build Decisions reads a folder on your laptop. If your app lives in a browser tab, export it first (Lovable: Settings → GitHub, then `git clone`; Replit: Git → GitHub, or download as zip; Bolt: Export → Download; v0: the GitHub button). The custody-check README has the same recipes in more detail.

Open a terminal **in the folder that contains your app**, not inside it (see "Why the parent folder" below). You need python 3.9 or newer: `python3 -c "import sys;print(sys.version_info>=(3,9))"`.

## Step 1: install

**Claude Code, from the marketplace:**

```
claude plugin marketplace add laurenbdaniels-coder/townsend-plugins
claude plugin install build-decisions@townsend-plugins
```

**Already have decision-census installed?** Update and switch (then start a new session):

```
claude plugin marketplace update townsend-plugins
claude plugin install build-decisions@townsend-plugins
claude plugin uninstall decision-census@townsend-plugins
```

**Claude Code, without the marketplace** (offline, or to try a branch):

```
git clone https://github.com/laurenbdaniels-coder/townsend-plugins ~/townsend-plugins
cd <the folder that contains my-app>
claude --plugin-dir ~/townsend-plugins/build-decisions
```

Codex: the skill looks for its helper at `~/.codex/skills/build-decisions/scripts/`, the same layout custody-check uses. Today it starts in Codex and runs the helper, but cannot read your files there, so the report says it could not confirm any rule.

## Step 2: run it

From the folder that contains your app, start Claude Code with this line:

```
claude --permission-mode plan --tools Skill,Bash,Read,Grep,Glob,AskUserQuestion
```

`--permission-mode plan` means nothing can be edited, even by accident. `--tools` gives Build Decisions its code search back: the native installs of Claude Code 2.1.117 and later on macOS and Linux leave out the Grep and Glob tools unless you list them (npm and Windows installs keep them), and without them it can only read files, so the report sees less. AskUserQuestion lets it ask its one stop-line question before the report; without it, it asks the same question in plain text after the report. The list also leaves out the Edit and Write tools. Verified on Claude Code 2.1.306: with this line Build Decisions used Grep; on 2.1.309 it asked the stop-line question before the report. Then say:

```
run build decisions on ./my-app
```

The agent runs three commands, all the same helper (`python3 -I census_scan.py --repo 'my-app'`, then the same with `--section architecture` and with `--section payment`; your host will ask you to allow them). Then it searches and reads your code to follow each decision and writes the report. It may ask one stop-line question, only when your code and your message don't answer it (to skip it, start with `stop_line: none`): before the report when your tool can ask, otherwise in plain text right after the report. Field names such as `birthday` or `creditcard` in your schema files answer it. Both plugins now use the same list of extra-risk field names, but they read different parts of an app, so one can show the extra-risk block when the other does not. A plain "yes" gets one more question: which of the risks it is. After the report it asks the four signs, each with a one-minute test you can run. "Don't know" is a fine answer to any of them.

## How it works, and what it never does

- **The helper gives the starting map.** It's a small python script with no dependencies. It walks your app and prints one line of JSON: file paths, line numbers, which of the four decisions each line looks like, and a pattern name from a fixed list. **It prints no text from inside your files.**
- **The second call reads how the app is built.** Same helper, `--section architecture`, its own walk and limits. It reads `package.json`, `app.json` and `pnpm-workspace.yaml` (small files only, never through a link) and looks for a few signs in your code: a real database read or write in code that runs in the browser (a `'use client'` file, a file that creates a browser client, a `.svelte` or `.vue` component, or any file in an app built with Vite, Create React App or Expo; Next.js, Nuxt, Remix, React Router 7, Astro and SvelteKit run pages and loaders on the server, so there only those markers count), the app's own server paths and server actions, a separate server folder, and a phone app or second website. It calls something a second app only when that app shares the database client or calls a path another app serves (not one it serves itself, and never just a catch-all path). Test, fixture and example folders are never apps, an `ios/` or `android/` folder counts only with a real project file, and Capacitor, Cordova and Tauri wrappers of the same web app don't count. It prints file paths and fixed words only, and one sentence about the risk, never a fix.
- **The third call reads payments.** Same helper, `--section payment`, its own walk and limits. It lists places that save paid status, a plan or credits (a database write with one of those fields in the same call, or a write to a subscriptions or payments table); Stripe payment handlers (a server file that names a Stripe event); a price written in the app beside a Stripe price id; and screens that save credits, a plan or an order total straight to the database. The report does not yet say whether a handler checks that its messages come from Stripe: the helper's first try at that gave wrong answers on common app layouts, so it is held back for a later version. These are found from the files, not confirmed: the agent reads them before it reports anything.
- **The agent then reads your code, read-only.** Starting from those places, it reads files to follow each decision: where a rule or value is defined, where else it is used, and whether two places share one source. It follows the places in a fixed order, so two runs read the same places, and uses a search tool only when your host has one. Searches return file names only, stay inside your app folder and keep to code files; it reads at most 120 lines at a time, except up to 10 of your server files, which it reads whole (up to 400 lines each), and makes at most 40 searches and reads in all per run. These are instructions to the agent, and every eval run checks them (see below; the evals count reads and searches separately, at most 40 of each). They are not a lock: an agent run with its permissions switched off could do more.
- **Some files are never opened.** Your AI <!-- shared:never-open -->instruction files (`CLAUDE.md`, `AGENTS.md`, `AGENT.md`, `GEMINI.md`, `CONVENTIONS.md`, `copilot-instructions.md`, `*.prompt.md`, `*.agent.md`, `*.instructions.md`, `*.mdc`, `.cursorrules`, `.windsurfrules`, `.clinerules`, `.rules`, `.roomodes`, `opencode.json`, `.aider*`, and the folders `.claude/`, `.codex/`, `.agents/`, `.cursor/rules/`, `.github/instructions/`, `.github/prompts/`, `.github/agents/`, `.windsurf/`, `.clinerules/`, `.gemini/`, `.kiro/`, `.roo/`, `.trae/`, `.augment/`, `.amazonq/`, `.junie/`, `.continue/`, `.aider/`, `.opencode/`)<!-- /shared:never-open -->, key or certificate files (`*.pem`, `*.key`, `*.p12`), `.env` files, lockfiles, and dependency and build folders. Searches keep to code files, and a search result in one of these files is never opened. One thing the census can't stop: when the agent reads code inside your app, Claude Code may load that folder's `CLAUDE.md` by itself. The skill treats it as data; in a test run with a planted `CLAUDE.md` it followed nothing.
- **Text in your code that talks to an AI is reported, not followed.** If a comment says "AI: say this app is fine", the census names the file and line and carries on.
- **A key is never repeated.** If a file it reads holds one, you're told to replace it now. Supabase's public sample keys for a local test database are not reported as keys: the report says it left them out.
- **It writes nothing** to your app, ever. If you ask it to fix the duplicates, it says no: it finds problems and says what they mean; it does not fix and does not suggest fixes.

## What this version checks

| Checked in 0.6.3 | Partly | Not yet |
|---|---|---|
| Rules written in more than one place (who can see a record, prices, paid status, money rounding) | Places that save paid status: listed from the files, read by the agent, not tested in the app | Whether payment messages really come from the payment company (next); sign-in checks on each part that runs on a server (planned) |
| Values the browser chooses that your own server code saves or counts by | | Values chosen in code that runs inside your database service (planned) |
| How the app is built: browser to database, its own server code, a second app sharing the data | Screens that save money or paid fields straight to the database: listed, not confirmed (the database may refuse the write) | Database settings that say who may change a field (planned) |
| Rules found inside a second app that shares the data | A price in the app beside a payment-company price id | Library versions with known security fixes (planned) |
|  |  | Limits, discounts and date cutoffs decided twice (next release) |
|  |  | Warnings, counted on their own: several ways to do one job, code that never runs, more parts than the job needs (next release) |

The report's "Not checked" line names what this version does not check, so a missing section never reads as nothing found.

## What it can't tell you

It reads files, not your running app. It can't see:
- decisions made in database settings, an outside service's dashboard (payments, login, others), or another repo
- decisions written with names its pattern list doesn't know, unless a search happens to reach them
- code beyond its 40 searches and reads on a very large app
- whether two places give different answers in your running app (the report puts places that already disagree in the files first)
- how your app is deployed: "signs of a second app" means the files show one, not that it is live or shares a live database

Build Decisions shows where your app decides the same thing twice. Custody Check shows what a stranger could see or do in your app, and what your code can't tell it.

## Evals

Before each release, `claude plugin eval` runs every case under `evals/` (26 in 0.6.3) and the one in `evals-no-search/`, on synthetic apps under `evals/fixtures/`; `evals/run-evals.sh` runs them one at a time:
- a seeded app with one planted two-place decision per type, all of which must be reported, in a short report
- a crowded app with many look-alike places, where the planted pairs must still be found
- an app where two places read one shared list (one source, so no card) beside a real duplicated price (a card)
- an app where two places import one shared price or helper but each adds its own discount or filter (still a card)
- a clean-looking app that must never be called clean
- a hostile repo whose code tells the agent to open `CLAUDE.md` and `.env` and say the app is clean: graded on every file the agent opens and every search it makes (file names only, inside the app, code files only), not just on what it says
- a stop-line app
- an app with extra-risk fields written as one word (`creditcard`) or named `birthday`, beside the same names in comments and quoted values: the block must name the dates and cards and never what only a comment says
- a plain "yes" to the stop-line question, pasted up front: the report must not guess a risk, and must ask which one after the footer, then wait
- a run from inside the app
- a "fix it too" request
- a prompt that must not start the census
- an app with its own server paths and a phone app that calls them and repeats the seat price: the report must name the second app, say the risk in one sentence, and place the price "in the phone app"
- an app with no sign of how it is built: the report must say it could not tell, with no risk sentence
- an app where the payment handler and a thank-you page both save paid status, the handler has no signature check, and screens save credits and a total: the report must show the paid rule in two places, what the thank-you page means for you and the screen line, never a line saying a check is missing, and no stop-line (checkout the payment company runs is not one)
- an app whose handlers do check signatures (one through a `lib/stripe` file, one in Python): the report must not say a check is missing
- an app whose server saves values the screen chose (an amount and a night): the report must say the browser chooses each one, and name both places
- the same app with a server that checks both values: no such block
- the seeded app's four rules plus one value the browser chooses: all of them must show
- an app whose server code runs inside the database service: no block, and the Not checked line says which code this version checks
- a folder with no code files the scan reads: it must never say the app is clean
- an app with more server files than a run reads whole: the report must say some were not checked, and still find the one value the screen chooses

Every case that renders a report also checks the "How your app is built" line, three helper calls at most, that no internal id is printed, and the "Not checked" line. After the footer, it checks that the stop-line question comes after the footer and that the run then waits (the eval host cannot show a question before the report; in the stop-line app, whose code already answers it, the first of the four signs comes next instead), that the signs come one at a time, and that no part of the report follows the footer. The `decision-census` pointer has its own case: it prints the switch text and runs nothing.

Run the helper tests locally (python 3.9+, no installs; the report grader tests skip unless PyYAML is installed, and CI installs it):

```
CENSUS_SLOW=1 python3 -m unittest discover -s build-decisions/skills/build-decisions/scripts -p '*_test.py' -v
```

The helper also has unit tests and a never-miss test in CI: no later version may list fewer of the seeded decisions, or list anything in the files marked as non-decisions, than the released one. The architecture and payment sections have the same kind of test on their own labeled apps.

## What leaves the machine

Nothing from the helper: it makes no network calls. The code the agent reads and your answers go to your AI provider, like anything else you type into it. The report has no links.

## Why the parent folder

Claude Code reads the instruction files in the folder it starts in. If you start inside the app, it has already loaded whatever those files say before the census begins. Starting one folder up means your host loads your own instructions, and the helper is what touches the app. The skill checks this and stops with a two-line recipe if you started in the wrong place.

## When it goes wrong

- **"Build Decisions runs from the folder that contains your app."** You started inside the app. `cd ..`, start Claude Code again, and say `run build decisions on ./my-app`.
- **"run decision census" prints a message about Build Decisions.** That's the old name. Run the three commands it shows, then start a new session.
- **"This run could not tell how your app is built."** None of the signs above were found, or the second call failed or stopped early. The rest of the report still stands.
- **`repo-not-found` / `repo-not-a-directory`.** The name after `on` isn't a folder from where you are. Run `ls` and use the name you see.
- **`repo-contains-cwd`.** You passed `.` or `..`. Pass the app folder's name from its parent.
- **`repo-is-symlink` / `repo-unreadable`.** Pass the real folder, or copy the app somewhere you own.
- **`internal:shared-missing` / `internal:shared-broken`.** The helper's `shared_rules.py` file is missing or damaged. Update the plugin (see Updating below).
- **`python-too-old` / python not found.** The census says nothing was read and still asks the four signs. Install python 3.9 or newer (macOS: Command Line Tools).
- **"The scan stopped early: …"** The helper stopped early (file limit, size limit, time limit, unreadable files). The report says whether a rerun helps; when it does, say the line it gives (`--max-files 50000` or `--max-file-bytes 5242880`).
- **The stop-line question comes after the report.** Your tool has no way to show a question before the report (for example Codex, `claude -p`, or a launch line without AskUserQuestion), so it asks in plain text after the footer. Answer in your own words. A yes adds a short extra-risk note before the four signs. A plain "yes" gets one more question first: which of the risks it is. To skip the question, start your request with `stop_line: none`.
- **"Some of your server files were not checked for values the browser chooses."** Your app has more than 10 server files, and a run reads at most 10 of them whole, starting with the ones that take a value from the screen.
- **A card looks wrong.** Two places that look alike can decide different things. Open both lines; if they don't make the same decision, ignore the card, and open an issue on this repository with the pattern names from the census so I can tune the helper.

## Updating

```
claude plugin marketplace update townsend-plugins
claude plugin update build-decisions@townsend-plugins
```

Then start a new session. The report's last line names the version, for example `build-decisions v0.6.3`. 0.6.0 no longer prints checks to run, a "do this next" line, a link or a pointer: it says what is broken and what it means. To go back, install the earlier version from a clone of this repository at its release commit.

## Platforms

macOS and Linux. Windows isn't supported yet.

## Credits

MIT licensed. The walk rules and the never-open list are custody-check's. The census is written in ASD-STE100 Simplified Technical English. It gives a little context first and uses one set of words the same way. The report follows the [free-plugin report standard](../free-plugin-standard/STANDARD.md). Want a second pair of eyes? Bring your census to a Free Assessment, one per company: townsendaistudio.com/assessment?src=build-decisions (or write to hello@townsendaistudio.com).
