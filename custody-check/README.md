# custody-check

I built this for the people who came to "It Said It Was Fine" at Seattle AI Week. It is the paper worksheet from that hour, made runnable: eleven questions about the app you vibe-coded, answered read-only from your own files plus what you tell it, and a plain report at the end: what is broken, what it means for you, and what your code can't tell. "Don't know" is an answer here. It is the useful one.

It runs inside Claude Code or Codex. It never changes your app, and the scanner makes no network calls; what does leave your machine is the redacted scan, the parts of your code the agent reads, and your answers, sent to the AI provider your host already uses (see What leaves the machine).

Build Decisions shows where your app decides who sees what and what things cost, and which rules it wrote more than once. Custody Check shows what a stranger could see or do in your app, and what your code can't tell it. Both are free and read-only.

## Step 0: get your code onto your machine

The check reads a folder on your laptop. If your app lives in a browser tab, get it out first. Each recipe ends in the same place: a folder on your machine that contains the app.

- **Lovable:** Settings → GitHub → Connect and push. Then on your machine: `git clone <the repository URL> my-app`.
- **Replit:** Tools → Git → connect to GitHub, then clone as above. Or: the three-dot menu → Download as zip, then unzip it into a folder called `my-app`.
- **Bolt:** Export → Download, then unzip into `my-app`.
- **v0:** the GitHub button on the project pushes it; then `git clone <URL> my-app`.
- **Cursor / Claude Code / anything local:** you already have the folder.

A zip export is fine. Without git history the check cannot tell whether you can get your code back, and the report lists that as an open question.

Now open a terminal **in the folder that contains `my-app`**, not inside `my-app`. This matters (see "Why the parent folder" below).

Prerequisites, one line to check:

```
python3 -c "import sys;print(sys.version_info>=(3,9))" && git --version && claude --version
```

If `python3` opens an installer on a fresh Mac, let it install the Command Line Tools and run the line again. If python is missing entirely, the check still runs: it reads your code and asks you the rest instead of scanning, and says so.

## Step 1: install

**Claude Code, from the marketplace** (two commands, run from anywhere):

```
claude plugin marketplace add laurenbdaniels-coder/townsend-plugins
claude plugin install custody-check@townsend-plugins
```

**Claude Code, without the marketplace** (offline, or to try a branch):

```
git clone https://github.com/laurenbdaniels-coder/townsend-plugins ~/townsend-plugins
cd <the folder that contains my-app>
claude --plugin-dir ~/townsend-plugins/custody-check
```

**Codex** (one copy command; re-run it to upgrade):

```
git clone https://github.com/laurenbdaniels-coder/townsend-plugins ~/townsend-plugins
mkdir -p ~/.codex/skills && cp -R ~/townsend-plugins/custody-check/skills/custody-check ~/.codex/skills/
```

## Step 2: run it

From the folder that contains your app, start your host (`claude` or `codex`) and say:

```
run custody-check on ./my-app
```

That phrase works in Claude Code. In Codex the phrase that worked in my own run was `use the custody-check skill on ./my-app` (the shorter "run X on ./my-app" made Codex step into the app folder first, which is what we are avoiding). If Codex does not find the skill, say `use the skill at ~/.codex/skills/custody-check on ./my-app`.

The agent runs three commands. First the scanner (retried only per script location, or once with `py -3`; `python3 -I custody_scan.py --repo ./my-app`; your host will ask you to allow it once). Then the inventory, the same script with `--inventory`, which lists your code files by name and line count and opens nothing it would not scan. Then it reads your code (search and read only, at most 40 calls), starting with the files that run on your server or save data. Then it asks you the questions it still cannot answer, one at a time. Then it runs the verdict script, which scans again and applies its written rule to the scan and your answers (`python3 -I custody_verdict.py --repo ./my-app --answers … --read … --expect …`). Then it prints the report. If the verdict script can't run, the agent says so and applies the written rule itself. Four to five minutes once the code is local.

Recommended: start Claude Code with this line, and never run it with `--dangerously-skip-permissions` for this check:

```
claude --permission-mode plan --tools Skill,Bash,Read,Grep,Glob,AskUserQuestion
```

`--permission-mode plan` means nothing can be edited, even by accident. `--tools` gives the check its code search back: the native installs of Claude Code 2.1.117 and later on macOS and Linux leave out the Grep and Glob tools unless you list them (npm and Windows installs keep them), and without them the check can only read files, so the report sees less. AskUserQuestion lets the host show the check's questions as a pick-list (seen for its stop-line question on Claude Code 2.1.309), and lets Build Decisions, run from the same session, ask its stop-line question before its report. The list also leaves out the Edit and Write tools. Verified on Claude Code 2.1.306: with this line the check used Grep. Plan mode alone was verified on 2.1.273: it allowed the scanner's read-only command and the run left the app untouched (`git status` unchanged, no newer files). If your version refuses it, run without plan mode and approve each `python3` prompt when it appears, or pass the narrowest rules your host accepts, anchored on the script and its flags. For a marketplace install that is three rules:

```
--allowedTools "Bash(python3 -I ~/.claude/plugins/*/custody-check/skills/custody-check/scripts/custody_scan.py --repo *)" \
  "Bash(python3 -I ~/.claude/plugins/*/custody-check/skills/custody-check/scripts/custody_scan.py --inventory --repo *)" \
  "Bash(python3 -I ~/.claude/plugins/*/custody-check/skills/custody-check/scripts/custody_verdict.py --repo *)"
```

For a clone, use the same three rules with the absolute path of your clone (`~/townsend-plugins/custody-check/skills/custody-check/scripts/`). Anchor each rule on the plugin's own path, never on a bare `*custody_scan.py`, so a file of that name inside the app can never match; it is a permission-prompt scope, not a sandbox, and never use a bare substring rule like `Bash(python3 *)`.

You can answer the questions up front instead of one at a time: paste a `Founder answers` block (the shape is in `skills/custody-check/assets/founder-answers-example.md`).

### What "done" looks like

The start of a real report, and one part of each section:

```
**We found 2 problems in your code, and 4 things your code can't tell us.**
Why this matters: a stranger can reach what your app does not protect. ...
We read all 6 of your code files.

**Do today:** replace 2 secret keys with new ones. Treat the old ones as already stolen.

## What we found in your code
**1. Anyone who visits your site can see your secret keys.**
What it means for you: a stranger can copy them, run up your bills on paid services, and read your whole database.
Where: `src/components/Config.tsx:2`, `src/lib/supabaseAdmin.ts:2`

## What your code can't tell us
These are not problems we found. The code can't answer them, so they are still open.
- **Whether you'd hear about it if your app broke.**
```

A problem is an answer the files, your code or you showed to be No. Everything the code can't settle is an open question, not a problem: it is the next thing to find out. "We read the files that could show it and found nothing" still leaves the live site open, because files cannot show the running app. Some apps carry extra risk: they handle card details themselves, hold other people's money, keep health or other sensitive data, or run at real scale. For those, a short block near the top says so and what a mistake there costs. Field names such as `birthday` or `creditcard` in your schema files count too. Both plugins now use the same list of extra-risk field names, but they read different parts of an app, so one can show the extra-risk block when the other does not. The report says what is broken and what it means; it does not say what to do, except to replace a key that may be exposed. The last line is the version.

## What it never does

- It never edits, deletes, or creates anything in your app. It finds issues and says what they mean. It does not fix anything or suggest fixes, even if you ask: no fix steps, and no prompt that changes your app. One safety step stays: a key that may be exposed is one to replace now.
- It never asks what your code should show: keys, what runs in the browser or on your server, who can read your data, who can change it. It reports what it found, and what it could not settle is an open question. It asks only what code can't show (backups, costs, alerts, what personal data you keep, exporting, whether it calls an AI model, and the extra-risk facts when the code doesn't show them), each with a one-minute test you can run to find the answer. The full scope is `free-plugin-standard/SCOPE.md`.
- The agent reads your code before it asks you anything, because the code can answer questions you may not know, such as who is allowed to delete a record. It reads only code files inside the app folder, at most 120 lines at a time and at most 40 searches and reads in all. It never opens `.env` files, key files, lockfiles, build folders or the instruction files below, and it never quotes a key or a line of your code: evidence is a path and a line number. The scanner prints redacted evidence (`sk-ab…43`, a path, a line number), never a key.
- The scanner never opens your AI <!-- shared:never-open -->instruction files (`CLAUDE.md`, `AGENTS.md`, `AGENT.md`, `GEMINI.md`, `CONVENTIONS.md`, `copilot-instructions.md`, `*.prompt.md`, `*.agent.md`, `*.instructions.md`, `*.mdc`, `.cursorrules`, `.windsurfrules`, `.clinerules`, `.rules`, `.roomodes`, `opencode.json`, `.aider*`, and the folders `.claude/`, `.codex/`, `.agents/`, `.cursor/rules/`, `.github/instructions/`, `.github/prompts/`, `.github/agents/`, `.windsurf/`, `.clinerules/`, `.gemini/`, `.kiro/`, `.roo/`, `.trae/`, `.augment/`, `.amazonq/`, `.junie/`, `.continue/`, `.aider/`, `.opencode/`)<!-- /shared:never-open -->. The list lives in the scanner (`NEVER_OPEN_DIRS`, `NEVER_OPEN_FILES`, `NEVER_OPEN_FILE_RE`) and no flag can shorten it. Under `.cursor/`, the `rules/` folder is never opened and `mcp.json` is read as an MCP config. An MCP config inside one of those never-opened folders (any file or folder with `mcp` in its name, except notes and instruction folders such as `skills/mcp-builder/`, `.kiro/settings/mcp.json`, `.gemini/settings.json` and the like), `opencode.json` or an `.aider*.yml` stays unopened too; `opencode.jsonc` is read as text like any other file, but its MCP servers are not checked. Each could hold a token, so it keeps Q1 at Don't know with an `mcp-config-not-opened` row.
- If AI drives part of your product, the check asks six more questions after the eleven, about keeping it on rails: how slow is too slow, where your prompts live, whether production is running what you tested, whether a change made things better rather than different, what a user sees when the model is wrong, and whether you would notice the model or your own product moving underneath. They are interview questions, not scanner ones. In the report, each one answered No is a problem and each Don't know is an open question.
- The scanner never follows a symlink (and refuses an app path that is one), never reads a lockfile, a source map, or a minified bundle, never reads a file over 512 KB, and stops at 20,000 files or 256 MB or two minutes and says so (`partial: yes`). A folder it could not read also makes the result partial rather than silently clean. The agent does not follow a symlink either: if your app folder itself is a shortcut, it asks before it reads anything there.
- On the line where it found a key it masks every other quoted string too, so a password sitting next to a key is not echoed either. Unquoted values on that line can still appear; the evidence rows are the only place app text reaches the chat.

## What leaves the machine

Nothing from the scanner: it makes no network calls. What the agent sees (the redacted JSON, the parts of your code it reads, and your answers) goes to your AI provider, like anything else you type into it. A key written into a code file it reads goes too, so a key the check finds in code is a key to replace. The report carries no link.

## Why the parent folder

Claude Code and Codex read the instruction files in the folder they start in (`CLAUDE.md`, `AGENTS.md`, `.cursor/rules`). If you start inside the app, the host has already loaded whatever those files say before this check begins, and an app built by an agent can contain instruction files nobody wrote on purpose. Starting one folder up means the host loads your own instructions at launch. The skill checks this and stops with a two-line recipe if you started in the wrong place. It cannot undo what the host loaded at launch, which is why the recipe says to relaunch. Once the agent reads a file inside the app, Claude Code also loads that folder's instruction files; the check treats them as app text and follows none of them.

## When it goes wrong

- **"This skill runs from the folder that contains your app."** You started inside the app. `cd ..`, start the host again, and say `run custody-check on ./my-app`.
- **`repo-not-found` / `repo-not-a-directory`.** The path after `on` is not a folder from where you are. Run `ls` and use the name you see.
- **`repo-unreadable`.** The folder's permissions block reading. Copy the app somewhere you own.
- **`python-too-old` / python not found.** The check reads your code, asks you the rest, and tells you it did not scan. Install python 3.9 or newer for the scan (macOS: Command Line Tools; Windows: `py -3`).
- **"The check stopped early: …"** The scanner stopped early (file limit, size limit, time limit, unreadable files); the line says why. When that leaves keys or open data unread, the next line gives the rerun: `run custody-check on ./my-app with --max-files 50000`. Or point it at the app subfolder.
- **`checks-not-finished` ("time ran out; rerun with --deadline-s 600").** 0.3.3 runs 0.3.2's checks first, then its own extra checks within a time budget. When those did not finish, Q1, Q3 and Q9 say Don't know instead of Nothing found. The key checks added in 0.6.2 run last with their own time: when only they ran out, only Q1 says Don't know. Ask the agent to rerun with `--deadline-s 600` (a longer limit gives the extra checks more time too). "an error; please report it" means the extra checks hit a bug: open an issue with that check name; 0.3.2's own answers above it still stand. "more found than the output can hold" means the checks finished but their rows did not fit the output; the answer is Don't know for the same reason.
- **`internal:release-missing` / `internal:release-modified` / `internal:shared-missing` / `internal:shared-broken`.** The scanner is three files (`custody_scan.py`, `custody_scan_0_3_2.py` and `shared_rules.py`) and one is missing or changed. Reinstall: in Claude Code, update the plugin; in Codex, re-run the `cp -R` command above, which copies the whole folder.
- **Is 0.3.3 being too cautious?** `CUSTODY_CHECK_OVERLAY=0` runs 0.3.2's checks alone (the output is 0.3.2's, labelled 0.3.3). The scanner's stderr line ends with `checks 0.3.3: finished|unfinished|error|skipped, N ms`; the skill does not show stderr, so this is for running the script by hand.
- **`git-not-a-repo`.** A zip export, or an export folder that is not tracked by git. Whether you can get your code back stays an open question.
- **`git-subdir`.** Your app folder is a tracked part of a larger repository (a monorepo). The commit and tag counts belong to the whole repository.
- **`repo-is-symlink`.** The app path is a symbolic link (a shortcut to another folder). Pass the real folder for the full check. Or say read it anyway: the agent then reads your code there without the scanner.
- **A git worktree.** The scanner treats a `.git` file that points outside the app folder as "not a repository", on purpose; run it on the main checkout instead.
- **`git-unavailable` / `git-timeout`.** Install git (macOS: Command Line Tools) or try again.
- **"I think a problem is wrong."** Each problem comes with a path and a line. Look there. If it really is a placeholder, a test fixture, or a public key, open an issue on this repository with the path and what you saw and I will tune it; the scanner cannot be argued down inside the chat, on purpose.
- **Windows.** Not supported for the workshop. The scanner's unit tests do run on Windows in CI, and most of them currently fail there (the git reader and the fifo, symlink and permission handling are written for macOS and Linux), so that job is informational and does not gate the build. Use macOS or Linux for the workshop; `py -3` in place of `python3` is enough to get the interview, not the scan.

### When something isn't read

Near the top, the coverage line says how much of your code was read:

- **"We read 40 of your 120 code files. Problems in the others can be missed."** The agent read the files where problems usually are, the ones that run on your server or save data, within its limit of 40 reads.
- **"We read 12 code files. Problems in files we did not read can be missed."** The inventory did not run, so the agent could not count your code files.

Under "We also can't see" at the end, each of these lines appears only when it applies:

- **"The check stopped early: …"** The scan reached a limit (files, size, time) or could not read some files; the line names which. When that leaves keys or open data unread, the next line gives the rerun: `run custody-check on ./my-app with --max-files 50000`.
- **"Could not list your code files (<code>)."** The inventory failed; the code names the reason (the same codes as above). The check carries on without the count.
- **"A newer reader for your database rules did not finish, so some protected tables may show as open."** The newer reader timed out or hit an error, so the older one's result stands. It is the cautious result: a table may show as open when it is protected.
- **"Your AI tool may have loaded this app's instruction files at launch."** You started inside the app. See "Why the parent folder".
- **"A file at `path:line` contains text addressed to an AI tool."** A file in your app talks to AI tools. The check treated it as data and did not follow it.

## From the workshop

The talk's worksheet stays here. The report does not print these lists.

The eleven questions:

1. Where do my secrets live? None in the browser.
2. Client or server? Anything the browser can see, a stranger can see.
3. Who can read this: logged out, the wrong user, the right user? Files too.
4. Who is allowed to do this? Logged in is not allowed.
5. Can I get the code back in five minutes, and the data back from a restored backup?
6. Is there a copy that isn't the live one?
7. What changed that I didn't ask for? Read the diff, not the summary.
8. What does one user cost me? A number or "I don't know".
9. How would I find out it's broken? One real alert to a named person.
10. What am I storing, and could I explain it out loud?
11. Can I export code and data and leave, and what did the platform default to?

Five, if you'll only do five:

1. Classify the next change against the Gated list in `skills/custody-check/references/tiers-and-doors.md`.
2. Boundary test: logged out, wrong user, right user; on each screen, each request a screen sends, each saved record and each uploaded file.
3. One full path on the live site, including any background job, email, payment message or AI call.
4. Read the changes line by line for surprises.
5. Prove you can go back to the last version, and get one real alert.

## Platforms

Workshop-supported: macOS and Linux. Windows: not supported (the unit tests run in CI there and most fail; the skill run has not been tried).

## Residual risk

The check is only as read-only as your host. Claude Code in plan mode and Codex's default sandbox both refuse writes; a host run with permissions switched off could still edit files if it decided to. The skill's rules forbid it and the report is the only output, but the rules are instructions, not a lock. The scanner runs `git` against the app's own `.git` folder with hooks, pagers, credential helpers and ssh disabled; git's own file-format parsers are the remaining surface, so a zip export from a stranger is best scanned without its `.git` folder.

## Why a scanner at all

Because the alternative is asking the agent to look for keys itself, and an agent that greps `.env` puts the key into the chat transcript. A small deterministic script can redact every string before the agent sees it. That is the whole reason the python file exists.

## Credits

Three detection patterns (the browser-exposed prefixes, "verify `.env` is in `.gitignore`", and the `USING (true)` row-security smells) are borrowed from [raroque/vibe-security-skill](https://github.com/raroque/vibe-security-skill), MIT. The report is written in ASD-STE100 Simplified Technical English. Everything else is the workshop handout.

MIT licensed. Want a second pair of eyes? Bring your report to a Free Assessment, one per company: townsendaistudio.com/assessment?src=custody-check (or write to hello@townsendaistudio.com).
