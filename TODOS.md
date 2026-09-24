# TODOS

## custody-check

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

### Q3 "nothing found" from a lone seed.sql

**What:** Any `.sql` file counts as a rule file, so a project whose only SQL is `supabase/seed.sql` (one `insert`) can reach Q3 Nothing found with "1 rule file read".

**Why:** `questions.md` promises that with no rule file the answer stays Don't know because rules live in a dashboard; a seed file is not a rule file. Found by the Claude adversarial pass in the v0.3.0 pre-merge review.

**Context:** `test_nothing_found_is_never_a_no_and_never_on_a_partial_scan` encodes the current rule (`select 1;` in a migration earns Nothing found), so this is a design change, not a bug fix: count a `.sql` file as a rule file only when it holds `create table`, `create policy`, `alter table … row level security` or `storage.buckets`; `.rules` and `database.rules.json` always count. Decide against the workshop corpus.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Q1 "nothing found" after one file, and file kinds Q1 never reads

**What:** Q1 Nothing found needs only one code or env file read, and `.xml`, `.plist`, `.properties`, `.prisma`, `.sh`, `.ini` are neither read for keys nor counted as gaps, although `EXPO_PUBLIC_` support puts mobile apps (`strings.xml`, `GoogleService-Info.plist`) in scope.

**Why:** The Q1 row says "N files read: no key in client code"; on a one-file repo or an Expo app that overstates what was checked.

**Context:** Raised by the Claude adversarial pass in the v0.3.0 pre-merge review. Options: a minimum file count for Q1, widening `Q1_Q3_EXTS` and `_pred_code_or_env`, or wording the row as what was actually read. Sits with the M5 precision pass.

**Effort:** M
**Priority:** P3
**Depends on:** M5 precision pass

### Smaller v0.3.0 review leftovers

**What:** Four evidence-only or observability items from the v0.3.0 pre-merge review, kept as designed for now: (1) `alter table t add column x, enable row level security` (comma-joined actions) is not recognised as enabling RLS, so `table-without-rls` can name a table that is covered; (2) the synthetic Q2 `client-server-split` and Q11 `code-history-local` rows are inserted at index 0 and can push out the twelfth real row without counting as trimmed; (3) `state.gaps` is never emitted, so a withheld Nothing found is indistinguishable in `stats` from the old "0 hits" (adding a `gaps` object to `stats` is contract-safe per SKILL.md); (4) MCP configs inside never-open agent folders (`.claude/settings.local.json`, `.kiro/settings/mcp.json`) are counted but not named in the Q1 row.

**Why:** None changes an answer or the door; each is a wording or visibility nit worth one small PR together.

**Context:** All from the Claude adversarial and maintainability passes on PR #11. (1) needs a bounded `[^;]{0,500}?` between the table name and `enable row level security` rather than an unbounded match. (2) either stop slicing after the insert (max 13 rows) or count the dropped row in `output_trimmed`; `test_json_shape` and the `MAX_EVIDENCE` assertions at test lines 936 and 1278 constrain the choice.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Open-rule shapes the Q3 "nothing found" row does not cover

**What:** The `nothing-found-rules` row now names exactly what was checked ("no RLS disabled, no using (true) policy, no if-true Firebase rule"), but three common open shapes pass every check: Firebase's generated test-mode default `allow read, write: if request.time < timestamp.date(...)`, Postgres `using (1=1)`, and `using (true or auth.uid() = owner)`. A rules file holding only those earns Q3 Nothing found.

**Why:** Time-boxed test mode is the most common vibe-coded Firebase layout. Found by the Red Team pass in the v0.3.0 pre-merge review; the row wording was fixed there, the detectors were not.

**Context:** Add `firebase-rules-test-mode` as an evidence row (`allow … : if request.time <`), and widen `USING_TRUE_RE` only as evidence (`policy-using-tautology`), never as a decisive `no`, until the workshop corpus shows no false positives. Also a judgement call from the same review: `.env-cmdrc` (env-cmd's rc file) is now a tracked env file for Q1 when committed; keep or exempt.

**Effort:** S
**Priority:** P2
**Depends on:** None

## Completed

### Test fixtures use real .env filenames

**What:** `scripts/fixtures/env_names/*/` contain files literally named `.env.production` and `.env.staging`. A tightened agent sandbox that denies reading `~/**/.env*` (a sensible default) makes `copy_fixture` fail with "Operation not permitted", and four tests error for a reason that has nothing to do with the code.

**Why:** The suite should not need the sandbox switched off to run.

**Context:** Hit on 2026-09-22 while scanning a corpus of local apps. Fix by storing the fixtures under a neutral name (`dotenv.production`) and renaming them during `copy_fixture`, so the bytes on disk never match an `.env*` deny rule.

**Effort:** S
**Priority:** P2
**Depends on:** None

**Completed:** v0.2.0 (2026-09-23)
