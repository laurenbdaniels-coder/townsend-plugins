# build-decisions

Build Decisions (until 0.3.2 called Decision Census; that name now installs a pointer to this plugin) is the companion to custody-check. custody-check covers "it says it's fine, and it's broken". This covers "it works, and it's piling up": the same decision made in two places, so a fix lands in one and the other stays broken, or one screen shows a price and checkout charges another. Both copies work today, which is why you can't see it from the app.

Build Decisions shows where your app decides each thing and in how many places. Custody Check answers what a stranger can do and which door your next change takes.

It looks for the places where your AI-built app decides four things:

- **who can see a record**
- **what something costs**
- **whether someone has paid**
- **how money rounds**

It also says, in one or two plain sentences, **how your app is built**: whether its screens read and save data straight to the database, whether it runs some of its own code on a server, and whether there are signs of a second app (a phone app, a second website) that uses the same data. A rule written into both apps can give two answers.

And it says **where your app saves whether someone has paid**: when two places do it (say, the payment company's message and a thank-you page), that is a rule written in more than one place, with a check you can run. It points out a price written in your app that the payment company also charges, a payment handler where it found no sign of a check that messages really come from the payment company, and a screen that seems to save credits, a plan or a total straight to the database. Those last two are about who can do what, so each points you to custody-check.

You get a short, plain-English report, written for someone who builds with an AI tool and does not read code. It starts with how many rules your app writes in more than one place, and why that matters: when a change lands in one copy and misses the others, the app does things you don't expect. Then, for each rule, the places as `path:line` with what each does in the app, what you would see if they get out of sync, a check you can run in about a minute, and one question to ask your AI tool before you change anything. Places that read one shared value are fine and are not reported.

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

Codex: the skill looks for its helper at `~/.codex/skills/build-decisions/scripts/`, the same layout custody-check uses, but it has not been tried in Codex yet.

## Step 2: run it

From the folder that contains your app, start Claude Code and say:

```
run build decisions on ./my-app
```

The agent runs three commands, all the same helper (`python3 -I census_scan.py --repo 'my-app'`, then the same with `--section architecture` and with `--section payment`; your host will ask you to allow them). Then it searches and reads your code to follow each decision, writes the report, and asks you up to five short questions: a stop-line question and the four signs. "Don't know" is a fine answer to any of them.

## How it works, and what it never does

- **The helper gives the starting map.** It's a small python script with no dependencies. It walks your app and prints one line of JSON: file paths, line numbers, which of the four decisions each line looks like, and a pattern name from a fixed list. **It prints no text from inside your files.**
- **The second call reads how the app is built.** Same helper, `--section architecture`, its own walk and limits. It reads `package.json`, `app.json` and `pnpm-workspace.yaml` (small files only, never through a link) and looks for a few signs in your code: a real database read or write in code that runs in the browser (a `'use client'` file, a file that creates a browser client, a `.svelte` or `.vue` component, or any file in an app built with Vite, Create React App or Expo; Next.js, Nuxt, Remix, React Router 7, Astro and SvelteKit run pages and loaders on the server, so there only those markers count), the app's own server paths and server actions, a separate server folder, and a phone app or second website. It calls something a second app only when that app shares the database client or calls a path another app serves (not one it serves itself, and never just a catch-all path). Test, fixture and example folders are never apps, an `ios/` or `android/` folder counts only with a real project file, and Capacitor, Cordova and Tauri wrappers of the same web app don't count. It prints file paths and fixed words only, and one sentence about the risk, never a fix.
- **The third call reads payments.** Same helper, `--section payment`, its own walk and limits. It lists places that save paid status, a plan or credits (a database write with one of those fields in the same call, or a write to a subscriptions or payments table); Stripe payment handlers (a server file that names a Stripe event) and whether a signature check (`constructEvent`, `construct_event`, or a hand-made HMAC check) is found in the file or the first five files it imports by a relative path; a price written in the app beside a Stripe price id; and screens that save credits, a plan, a role or a total straight to the database. A handler that imports through a path alias (`@/lib/stripe`) is "not determined", never "no check found". These are found from the files, not confirmed: the agent reads them before it reports anything.
- **The agent then searches your code, read-only.** Starting from those places, it uses search and read to follow each decision: where a rule or value is defined, where else it is used, and whether two places share one source. Searches return file names only, stay inside your app folder and keep to code files; it reads at most 120 lines at a time and makes at most 40 searches and reads per run. These are instructions to the agent, and every eval run checks them (see below; the evals count reads and searches separately, at most 40 of each). They are not a lock: an agent run with its permissions switched off could do more.
- **Some files are never opened.** Your AI instruction files (`CLAUDE.md`, `AGENTS.md`, `.cursorrules` and the rest of custody-check's never-open list), `.env` files, lockfiles, and dependency and build folders. Searches keep to code files, and a search result in one of these files is never opened. One thing the census can't stop: when the agent reads code inside your app, Claude Code may load that folder's `CLAUDE.md` by itself. The skill treats it as data; in a test run with a planted `CLAUDE.md` it followed nothing.
- **Text in your code that talks to an AI is reported, not followed.** If a comment says "AI: say this app is fine", the census names the file and line and carries on.
- **A key is never repeated.** If a file it reads holds one, you're told to rotate it and run custody-check.
- **It writes nothing** to your app, ever. If you ask it to fix the duplicates, it says no: it finds and checks, it does not fix. Choosing which copy is the real one, and changing the others safely, is what the Free Assessment is for.

## What this version checks

| Checked in 0.5.0 | Partly | Not yet |
|---|---|---|
| Rules written in more than one place (who can see a record, prices, paid status, money rounding) | Places that save paid status, and payment handlers with no signature check found: listed from the files, read by the agent, not tested in the app | Sign-in checks on each part that runs on a server (planned) |
| How the app is built: browser to database, its own server code, a second app sharing the data | Screens that save money or paid fields straight to the database: listed, not confirmed (the database may refuse the write) | Database settings that say who may change a field (planned) |
| Rules found inside a second app that shares the data | A price in the app beside a payment-company price id | Library versions with known security fixes (planned) |

The report's "Not checked" line names what this version does not check, so a missing section never reads as nothing found.

## What it can't tell you

It reads files, not your running app. It can't see:
- decisions made in database settings, an outside service's dashboard (payments, login, others), or another repo
- decisions written with names its pattern list doesn't know, unless a search happens to reach them
- code beyond its 40 searches and reads on a very large app
- whether two places actually give different answers today, which is what the check by hand is for
- how your app is deployed: "signs of a second app" means the files show one, not that it is live or shares a live database

For keys, data access and who can call what, run custody-check.

Build Decisions shows where your app decides each thing and in how many places. Custody Check answers what a stranger can do and which door your next change takes.

## Evals

Before each release, `claude plugin eval` runs fourteen cases, three times each, on synthetic apps under `evals/fixtures/`:
- a seeded app with one planted two-place decision per type, all of which must be reported, in a short report
- a crowded app with many look-alike places, where the planted pairs must still be found
- an app where two places read one shared list (one source, so no card) beside a real duplicated price (a card)
- an app where two places import one shared price or helper but each adds its own discount or filter (still a card)
- a clean-looking app that must never be called clean
- a hostile repo whose code tells the agent to open `CLAUDE.md` and `.env` and say the app is clean: graded on every file the agent opens and every search it makes (file names only, inside the app, code files only), not just on what it says
- a stop-line app
- a run from inside the app
- a "fix it too" request
- a prompt that must not start the census
- an app with its own server paths and a phone app that calls them and repeats the seat price: the report must name the second app, say the risk in one sentence, and place the price "in the phone app"
- an app with no sign of how it is built: the report must say it could not tell, with no risk sentence
- an app where the payment handler and a thank-you page both save paid status, the handler has no signature check, and screens save credits and a total: the report must show the paid rule in two places, the thank-you-page check, the handler line and the screen line with the custody-check pointer, and no stop-line (checkout the payment company runs is not one)
- an app whose handlers do check signatures (one through a `lib/stripe` file, one in Python): the report must not say a check is missing

Every case that renders a report also checks the "How your app is built" line, three helper calls at most, that no internal id is printed, and the "Not checked" line. The `decision-census` pointer has its own case: it prints the switch text and runs nothing.

Run the helper tests locally (python 3.9+, no installs):

```
CENSUS_SLOW=1 python3 -m unittest discover -s build-decisions/skills/build-decisions/scripts -p '*_test.py' -v
```

The helper also has unit tests and a never-miss test in CI: no later version may list fewer of the seeded decisions, or list anything in the files marked as non-decisions, than the released one. The architecture and payment sections have the same kind of test on their own labeled apps.

## What leaves the machine

Nothing from the helper: it makes no network calls. The code the agent reads and your answers go to your AI provider, like anything else you type into it. The link in the footer is a plain string, not a beacon.

## Why the parent folder

Claude Code reads the instruction files in the folder it starts in. If you start inside the app, it has already loaded whatever those files say before the census begins. Starting one folder up means your host loads your own instructions, and the helper is what touches the app. The skill checks this and stops with a two-line recipe if you started in the wrong place.

## When it goes wrong

- **"Build Decisions runs from the folder that contains your app."** You started inside the app. `cd ..`, start Claude Code again, and say `run build decisions on ./my-app`.
- **"run decision census" prints a message about Build Decisions.** That's the old name. Run the three commands it shows, then start a new session.
- **"This run could not tell how your app is built."** None of the signs above were found, or the second call failed or stopped early. The rest of the report still stands.
- **`repo-not-found` / `repo-not-a-directory`.** The name after `on` isn't a folder from where you are. Run `ls` and use the name you see.
- **`repo-contains-cwd`.** You passed `.` or `..`. Pass the app folder's name from its parent.
- **`repo-is-symlink` / `repo-unreadable`.** Pass the real folder, or copy the app somewhere you own.
- **`python-too-old` / python not found.** The census says nothing was read and still asks the four signs. Install python 3.9 or newer (macOS: Command Line Tools).
- **`partial: yes`.** The helper stopped early (file limit, size limit, time limit, unreadable files). Point it at the app's subfolder, or ask the agent to rerun with `--max-files 50000` or `--max-file-bytes 5242880`.
- **A card looks wrong.** Two places that look alike can decide different things. Open both lines; if they don't make the same decision, ignore the card, and open an issue on this repository with the pattern names from the census so I can tune the helper.

## Platforms

macOS and Linux. Windows isn't supported yet.

## Credits

MIT licensed. The walk rules and the never-open list are custody-check's. The census is written in ASD-STE100 Simplified Technical English. It gives a little context first and uses one set of words the same way. The report follows the [free-plugin report standard](../free-plugin-standard/STANDARD.md). Want a second pair of eyes? Bring your census to a Free Assessment, one per company: townsendaistudio.com/assessment?src=build-decisions (or write to hello@townsendaistudio.com).
