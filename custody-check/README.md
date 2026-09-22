# custody-check

I built this for the people who came to "It Said It Was Fine" at Seattle AI Week. It is the paper worksheet from that hour, made runnable: eleven questions about the app you vibe-coded, answered read-only from your own files plus what you tell it, and a verdict at the end: ship it, patch it, or shelve it. "Don't know" is an answer here. It is the useful one.

It runs inside Claude Code or Codex. It never changes your app, and the scanner makes no network calls; what does leave your machine is the redacted scan and your answers, sent to the AI provider your host already uses (see What leaves the machine).

## Step 0: get your code onto your machine

The check reads a folder on your laptop. If your app lives in a browser tab, get it out first. Each recipe ends in the same place: a folder on your machine that contains the app.

- **Lovable:** Settings → GitHub → Connect and push. Then on your machine: `git clone <the repository URL> my-app`.
- **Replit:** Tools → Git → connect to GitHub, then clone as above. Or: the three-dot menu → Download as zip, then unzip it into a folder called `my-app`.
- **Bolt:** Export → Download, then unzip into `my-app`.
- **v0:** the GitHub button on the project pushes it; then `git clone <URL> my-app`.
- **Cursor / Claude Code / anything local:** you already have the folder.

A zip export is fine. The check tells you what it cannot see without git history (Q5's code half) and how to answer it by hand.

Now open a terminal **in the folder that contains `my-app`**, not inside `my-app`. This matters (see "Why the parent folder" below).

Prerequisites, one line to check:

```
python3 -c "import sys;print(sys.version_info>=(3,9))" && git --version && claude --version
```

If `python3` opens an installer on a fresh Mac, let it install the Command Line Tools and run the line again. If python is missing entirely, the check still runs: it interviews you instead of scanning, and says so.

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

The agent runs one command, the scanner (retried only per script location, or once with `py -3`; `python3 -I custody_scan.py --repo ./my-app`; your host will ask you to allow it once), then asks you the questions it cannot answer from files, one at a time, then prints the verdict. Four to five minutes once the code is local. Recommended: start Claude Code with `claude --permission-mode plan` so nothing can be edited even by accident, and never run it with `--dangerously-skip-permissions` for this check. Verified on Claude Code 2.1.273: plan mode allowed the scanner's one read-only command and the run left the app untouched (`git status` unchanged, no newer files). If your version refuses it, run without plan mode and approve the single `python3` prompt when it appears, or pass the narrowest rule your host accepts, anchored on the script and its flag: `--allowedTools "Bash(python3 -I ~/.claude/plugins/*/custody-check/skills/custody-check/scripts/custody_scan.py --repo *)"` for a marketplace install, or the same rule with the absolute path of your clone (`~/townsend-plugins/custody-check/skills/custody-check/scripts/custody_scan.py`). Anchor the rule on the plugin's own path, never on a bare `*custody_scan.py`, so a file of that name inside the app can never match; it is a permission-prompt scope, not a sandbox, and never use a bare substring rule like `Bash(python3 *)`.

You can answer the questions up front instead of one at a time: paste a `Founder answers` block (the shape is in `skills/custody-check/assets/founder-answers-example.md`).

### What "done" looks like

Three rows of a real verdict:

```
| 1 | Secrets out of the browser | no | high | `src/lib/config.ts:12` · `browser-prefix-service-or-secret-name` |
| 3 | Who can read this | don't know | med | 128 files scanned, 0 hits |
| 9 | How I'd find out it's broken | don't know | low | (you: "I'd hear it from a user") |
```

followed by the door ("Patch it: Q1, then Q9"), the five-if-only-five list, the Don't-know list with a sixty-second test for each, and the footer with the version and file count.

## What it never does

- It never edits, deletes, or creates anything in your app. If you ask it to fix something, it answers with the Patch list instead.
- The agent never opens your files. The scanner is the only thing that reads them, and it prints redacted evidence (`sk-ab…43`, a path, a line number), never a key.
- The scanner never opens your AI instruction files: `CLAUDE.md`, `AGENTS.md`, `AGENT.md`, `GEMINI.md`, `CONVENTIONS.md`, `copilot-instructions.md`, any `*.prompt.md`, `*.agent.md`, `*.instructions.md` or `*.mdc`, `.cursorrules`, `.windsurfrules`, `.clinerules`, `.rules`, `.roomodes`, `opencode.json`, `.aider*`, the folders `.agents/`, `.aider/`, `.amazonq/`, `.augment/`, `.claude/`, `.clinerules/`, `.codex/`, `.continue/`, `.gemini/`, `.junie/`, `.kiro/`, `.opencode/`, `.roo/`, `.trae/`, `.windsurf/`, plus `.cursor/rules/`, `.github/instructions/`, `.github/prompts/` and `.github/agents/`. The list lives in the scanner (`NEVER_OPEN_DIRS`, `NEVER_OPEN_FILES`, `NEVER_OPEN_FILE_RE`) and no flag can shorten it. Under `.cursor/`, the `rules/` folder is never opened and `mcp.json` is read as an MCP config.
- It never follows a symlink (and refuses an app path that is one), never reads a lockfile, a source map, or a minified bundle, never reads a file over 512 KB, and stops at 20,000 files or 256 MB or two minutes and says so (`partial: yes`). A folder it could not read also makes the result partial rather than silently clean.
- On the line where it found a key it masks every other quoted string too, so a password sitting next to a key is not echoed either. Unquoted values on that line can still appear; the evidence rows are the only place app text reaches the chat.

## What leaves the machine

Nothing from the scanner: it makes no network calls. What the agent sees (the redacted JSON and your answers) goes to your AI provider, like anything else you type into it. The link in the footer is a plain string you can click or not; it is not a beacon.

## Why the parent folder

Claude Code and Codex read the instruction files in the folder they start in (`CLAUDE.md`, `AGENTS.md`, `.cursor/rules`). If you start inside the app, the host has already loaded whatever those files say before this check begins, and an app built by an agent can contain instruction files nobody wrote on purpose. Starting one folder up means the host loads your own instructions, and the scanner is what touches the app. The skill checks this and stops with a two-line recipe if you started in the wrong place. This guard protects the scanner's reads; it cannot undo what the host loaded at launch, which is why the recipe says to relaunch.

## When it goes wrong

- **"This skill runs from the folder that contains your app."** You started inside the app. `cd ..`, start the host again, and say `run custody-check on ./my-app`.
- **`repo-not-found` / `repo-not-a-directory`.** The path after `on` is not a folder from where you are. Run `ls` and use the name you see.
- **`repo-unreadable`.** The folder's permissions block reading. Copy the app somewhere you own.
- **`python-too-old` / python not found.** The check continues as an interview and tells you it did not scan. Install python 3.9 or newer for the scan (macOS: Command Line Tools; Windows: `py -3`).
- **`partial: yes`.** The scanner stopped early; the footer says why (file limit, byte budget, time limit, unreadable files). Point it at the app subfolder or re-run with `--max-files 50000` if you asked the agent to pass flags.
- **`git-not-a-repo`.** A zip export, or an export folder that is not tracked by git. Q5's code half stays "don't know"; the by-hand test is in the Don't-know list.
- **`git-subdir`.** Your app folder is a tracked part of a larger repository (a monorepo). The commit and tag counts belong to the whole repository.
- **`repo-is-symlink`.** The app path is a symbolic link; pass the real folder.
- **A git worktree.** The scanner treats a `.git` file that points outside the app folder as "not a repository", on purpose; run it on the main checkout instead.
- **`git-unavailable` / `git-timeout`.** Install git (macOS: Command Line Tools) or try again.
- **"I think a `no` is wrong."** A scanner `no` comes with a path and a line. Look there. If it really is a placeholder, a test fixture, or a public key, open an issue on this repository with the check name from the evidence column and I will tune it; the scanner cannot be argued down inside the chat, on purpose.
- **Windows.** Not supported for the workshop. The scanner's unit tests do run on Windows in CI, and most of them currently fail there (the git reader and the fifo, symlink and permission handling are written for macOS and Linux), so that job is informational and does not gate the build. Use macOS or Linux for the workshop; `py -3` in place of `python3` is enough to get the interview, not the scan.

## Platforms

Workshop-supported: macOS and Linux. Windows: not supported (the unit tests run in CI there and most fail; the skill run has not been tried).

## Residual risk

The check is only as read-only as your host. Claude Code in plan mode and Codex's default sandbox both refuse writes; a host run with permissions switched off could still edit files if it decided to. The skill's rules forbid it and the Patch list is the only output, but the rules are instructions, not a lock. The scanner runs `git` against the app's own `.git` folder with hooks, pagers, credential helpers and ssh disabled; git's own file-format parsers are the remaining surface, so a zip export from a stranger is best scanned without its `.git` folder.

## Why a scanner at all

Because the alternative is asking the agent to look for keys itself, and an agent that greps `.env` puts the key into the chat transcript. A small deterministic script can redact every string before the agent sees it. That is the whole reason the python file exists.

## Credits

Three detection patterns (the browser-exposed prefixes, "verify `.env` is in `.gitignore`", and the `USING (true)` row-security smells) are borrowed from [raroque/vibe-security-skill](https://github.com/raroque/vibe-security-skill), MIT. Everything else is the workshop handout.

MIT licensed. Want the routing I run? Send your verdict to hello@townsendaistudio.com, or use the link in the footer: townsendaistudio.com/?src=custody-check
