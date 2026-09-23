# TODOS

## custody-check

### Should build-output folders keep Q1 off "nothing found"?

**What:** Decide whether a `dist/`, `build/`, `out/` or `.next/` folder on disk should count as a gap for Q1, the way a minified bundle in `public/` now does.

**Why:** Both adversarial reviewers of v0.3.0 flagged that a key baked into a build sits in a folder the scanner never reads, while Q1 can say "Nothing found". Kept as designed for now: those folders are regenerated from source on every build, almost every local Next.js checkout has a `.next/`, and counting them would switch "nothing found" off for nearly every app. The deployed-site by-hand test is what catches a baked-in key, and `questions.md` says so.

**Context:** A middle option is to count the folder only when git tracks it (a committed `dist/` is served as-is from a public repo). That needs one more `ls-files` call inside `git_facts`, whose time budget is shared. Revisit with the Oct 12 precision pass on real Lovable, Bolt, v0 and Replit exports.

### Paste-prompt single-file fallback

**What:** Flatten `SKILL.md` plus `references/` into one paste-able prompt for attendees who have no CLI at all.

**Why:** Some Lovable, Replit and Bolt users never install anything; the degraded interview path covers most of the value, but only from inside a host that has the skill.

**Context:** Deferred at the 2026-09-17 plan gate (CEO E10, DX taste). Would be a generated artifact that must be regenerated whenever the skill text changes; it has no scanner, so no evidenced answers. Start from `custody-check/skills/custody-check/SKILL.md` and the two references; add a CI step that fails when the flattened file is stale.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Make the scanner work on Windows

**What:** 116 of the scanner's unit tests fail on the `windows-latest` CI job. The git reader (non-blocking pipes, `select`, process groups), the fifo and symlink guards, and the permission and temp-directory handling in the tests are all written for macOS and Linux.

**Why:** The workshop is macOS and Linux only, so this does not block the giveaway, but a Windows attendee currently gets the by-hand interview with no scan. The job already runs and is informational, so the failure count is visible.

**Context:** The CI job is `custody-check-windows` in `.github/workflows/ci.yml`, kept `continue-on-error: true` until it is green. The plan's drop order named the Windows job as the first thing to cut, and it was cut. Start with the threaded reader path in `git_facts` (already written for platforms without non-blocking pipes) and the `tearDown` permission handling in `ScanCase`.

**Effort:** L
**Priority:** P3
**Depends on:** None

### Stream large directory listings

**What:** Walk with `os.scandir` and stop consuming a directory once `MAX_DIR_ENTRIES` entries have been seen, instead of letting `os.walk` build and sort the whole listing first.

**Why:** A single folder with millions of entries costs the full listing in memory and an O(n log n) sort before the cap can bite. The caps bound the work done per directory, not the cost of learning what is in it.

**Context:** Raised by the performance specialist and the Codex adversarial pass in the pre-merge review of PR 1 and accepted as a known limit. `run_scan` in `custody_scan.py` (the `MAX_DIR_ENTRIES` branch) and `count_files` are the two places.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Decide what `src/lib` means in a Vite app

**What:** Today a file under a neutral segment (`lib`, `utils`, `services`, ...) is client code only when it imports a UI framework or carries a `use client` directive. In a Vite or plain SPA build, everything under `src/` is bundled for the browser.

**Why:** A hardcoded service key in `src/lib/supabase.ts` is evidence rather than a decisive Q1 `no`. That is deliberate (the same rule stops Next.js server helpers producing false positives), but the tradeoff should be re-decided against real builder exports.

**Context:** Raised by the Codex adversarial pass in the pre-merge review of PR 1 and kept as designed. The M5 precision pass on public builder templates is the right place to settle it: if Vite exports dominate, gate the rule on the presence of `next.config.*` instead.

**Effort:** M
**Priority:** P2
**Depends on:** M5 precision pass

### Scanner readability pass

**What:** Fold the review's accepted style findings into one pass: named constants for the line-clip and run-walk bounds, inline regexes promoted beside the others, `ScanFile.is_env` as a slot, an `ENV_NAME_HANDLERS` table, one `_dumps` helper shared by `_fit_output` and `emit`, and test classes named by subject rather than by review cycle.

**Why:** None of these change behaviour, and each one is a place where two definitions can drift apart.

**Context:** Collected from the maintainability and simplification specialists across three review cycles of PR 1; all were recorded as advisory and skipped to keep the review converging.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Byte-ratio binary heuristic

**What:** Detect binary files by the ratio of non-text bytes instead of only a NUL in the first 8 KB.

**Why:** A few binary formats without early NULs get decoded and scanned noisily; a few text files with a stray NUL get skipped.

**Context:** Deferred at the Eng phase (Codex C6). `decode_text()` in `custody_scan.py` is the single place to change; count the new skip reason in `stats`.

**Effort:** S
**Priority:** P3
**Depends on:** None

### `--git-timeout` flag

**What:** Expose the 15 s git budget as a flag.

**Why:** Very large repositories on slow disks can exceed the budget and report `git-timeout`.

**Context:** Declined for v0.1.0 (YAGNI). `GIT_BUDGET_S` in `custody_scan.py`.

**Effort:** S
**Priority:** P3
**Depends on:** None

### skills.sh listing

**What:** List custody-check on skills.sh / `npx skills add`.

**Why:** One-command install through the channel vibe-coders already use.

**Context:** Kept out of scope by the design; revisit after the workshop shows whether attendees install at all.

**Effort:** S
**Priority:** P3
**Depends on:** PR 2 evals

### Hosted demo sandbox

**What:** A public "try it without your own code" demo.

**Why:** Time-to-first-verdict without an export step.

**Context:** Declined: the design promise is that nothing leaves the machine. The PR 2 seeded-app fixture will double as a clonable demo folder linked from the README instead.

**Effort:** L
**Priority:** P4
**Depends on:** PR 2 evals

## Completed

### Test fixtures use real .env filenames

**What:** `scripts/fixtures/env_names/*/` contain files literally named `.env.production` and `.env.staging`. A tightened agent sandbox that denies reading `~/**/.env*` (a sensible default) makes `copy_fixture` fail with "Operation not permitted", and four tests error for a reason that has nothing to do with the code.

**Why:** The suite should not need the sandbox switched off to run.

**Context:** Hit on 2026-09-22 while scanning a corpus of local apps. Fix by storing the fixtures under a neutral name (`dotenv.production`) and renaming them during `copy_fixture`, so the bytes on disk never match an `.env*` deny rule.

**Effort:** S
**Priority:** P2
**Depends on:** None

**Completed:** v0.2.0 (2026-09-23)


