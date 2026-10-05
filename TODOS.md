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

### Q1 "nothing found" after one file, and file kinds Q1 never reads

**What:** Q1 Nothing found needs only one code or env file read, and `.xml`, `.plist`, `.properties`, `.prisma`, `.sh`, `.ini` are neither read for keys nor counted as gaps, although `EXPO_PUBLIC_` support puts mobile apps (`strings.xml`, `GoogleService-Info.plist`) in scope.

**Why:** The Q1 row says "N files read: no key in client code"; on a one-file repo or an Expo app that overstates what was checked.

**Context:** Raised by the Claude adversarial pass in the v0.3.0 pre-merge review. Options: a minimum file count for Q1, widening `Q1_Q3_EXTS` and `_pred_code_or_env`, or wording the row as what was actually read. Sits with the M5 precision pass.

**Effort:** M
**Priority:** P3
**Depends on:** M5 precision pass

### Smaller v0.3.0 review leftovers

**What:** Four evidence-only or observability items from the v0.3.0 pre-merge review, kept as designed for now: (1) `alter table t add column x, enable row level security` (comma-joined actions) is not recognised as enabling RLS, so `table-without-rls` can name a table that is covered; (2) the synthetic Q2 `client-server-split` and Q11 `code-history-local` rows are inserted at index 0 and can push out the twelfth real row without counting as trimmed; (3) `state.gaps` is never emitted, so a withheld Nothing found is indistinguishable in `stats` from the old "0 hits" (adding a `gaps` object to `stats` is contract-safe per SKILL.md); (4) `.claude/settings.local.json` can carry MCP server env tokens but is counted as an agent file, not a Q1 gap (the MCP-only paths such as `.kiro/settings/mcp.json` became `mcp-config-not-opened` gaps in 0.3.3); every Claude Code project has one, so gating Q1 on it needs the workshop corpus first.

**Why:** None changes an answer or the door; each is a wording or visibility nit worth one small PR together.

**Context:** All from the Claude adversarial and maintainability passes on PR #11. (1) needs a bounded `[^;]{0,500}?` between the table name and `enable row level security` rather than an unbounded match. (2) either stop slicing after the insert (max 13 rows) or count the dropped row in `output_trimmed`; `test_json_shape` and the `MAX_EVIDENCE` assertions in `custody_scan_test.py` constrain the choice.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Door rule when Q1 or Q3 is Don't know on a complete scan

**What:** Step 3 of the door rule blocks Ship it only when the scan was partial. A build folder, a minified bundle, a precompressed bundle or an excluded folder withholds Nothing found (a gap) without making the scan partial, so Q1 can be an ordinary Don't know on a `partial: false` result and step 5 can still reach Ship it.

**Why:** Raised by the Codex adversarial pass in the v0.3.0 pre-merge review. It is the v0.2.0 behaviour too (an excluded folder never set partial), so it is not a regression, but the gap counters now make the distinction visible and the door rule could use it.

**Context:** Options: emit `stats.gaps` (see the leftovers entry) and let step 3 read "partial, or Q1/Q3 withheld by a gap"; or keep the door as is and have the verdict name the gap in the Q1 row. Decide against the workshop corpus so ordinary prototypes with a `build/` folder are not pushed to Patch it.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Open-rule shapes the Q3 "nothing found" row still does not cover

**What:** After 0.3.3 (test mode, `if (true)`, string literals, dropped tables and public views), three shapes still pass every Q3 check: Postgres `using (1=1)`, `using (true or auth.uid() = owner)`, and `using (auth.uid() is not null)`, which lets every signed-in user read every row.

**Why:** A rules file holding only those earns Q3 Nothing found. Found by the adversarial passes in the v0.3.0 pre- and post-merge reviews.

**Context:** Widen `USING_TRUE_RE` only as evidence (`policy-using-tautology`, `policy-any-signed-in`), never as a decisive `no`, until the workshop corpus shows no false positives. Also: a committed `.env-cmdrc` is `tracked-env-file-nonprod` evidence while `.env-cmdrc.json` is a tracked env file (`no`); both usually hold every environment, production included, so pick one rule.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Q1 and Q3 claims the file tree cannot settle

**What:** (1) A `.env` committed and later `git rm --cached` still holds its key in history, but Q1 says "no tracked env file". (2) The scanner does not replay migration order across files, so 0.3.3 withholds Nothing found on any cross-file drop; it could order `supabase/migrations/*` by filename instead. (3) A down migration (`*.down.sql`) that disables RLS gives Q3 a high-confidence `no` for a state production never runs.

**Why:** Each is either a false reassurance (1) or a false alarm (2, 3). From the v0.3.0 post-merge adversarial review.

**Context:** (1) `git log --all --diff-filter=A --name-only -- ':(icase).env*'` inside the existing git budget, or say in the row that history was not checked. (3) treat `*.down.sql` and `down/` as evidence-only for `rls-disabled`.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Leftovers from the v0.3.3 review

**What:** (1) A `;` or `}` inside a Firebase string or map literal before `|| true` (`'a;b' || true`, `{'a': 1} || true`), and a URL in a condition string (`== 'https://x.com' || true`, where the `//` strip eats the rest of the line), still end the condition early, so Q3 can read Nothing found; same on 0.3.2. (2) A Supabase edge function importing `npm:@sentry/deno` with no manifest is not seen by Q9. (3) Never-open folder lookups are case-sensitive on Linux (`.Roo/MCP.json`), matching the tools themselves there. (4) A file of only `drop table` statements reports "no SQL or security-rules file among them", though one was read.

**Why:** (1) is a false Nothing found on a realistic rule (the URL case); the rest are wording or reach. From the adversarial and Codex passes on the v0.3.3 branch.

**Context:** (1) lex Firebase rules the way `_lex_sql` lexes SQL (strings and `//` comments in one pass) before reading conditions. (2) a code-import check for `npm:@sentry/` and `jsr:` specifiers under `supabase/functions/`.

**Effort:** S
**Priority:** P2 for (1), P3 for the rest
**Depends on:** None

### Leftovers from the pre-merge review of PR #24 (2026-10-01)

**What:** (1) Text that names a view inside a SQL string (`comment on table … is 'create view public.v as …'`) is a `public-view` row, so Q3 says Don't know where no view is created. (2) Some answers 0.3.3 holds back to match 0.3.2 are wrong in 0.3.2's direction: an `enable row level security` after a `'--'` or `'/*'` string, or with a comment longer than 20 spaces inside it, really runs, but RLS credit is capped at what 0.3.2 read, so Q3 stays at Don't know. (3) `_mcp_configs_inside` walks a never-open folder a second time after `count_files` (see "One walk per never-open folder"). (4) Two prefilter timing tests (`test_prefilter_repeated_keyword_is_linear`, `test_prefilter_accepts_keyish_identifiers_and_stays_linear`) miss their 1.0 s bound under load; they time a regex main also has.

**Why:** (1) and (2) are cautious answers that are not needed: (1) reads strings for bad signals on purpose, since `EXECUTE '…'` runs them; (2) follows the never-worse rule. (3) is cost, measured as linear (a 560 KB migration takes 1.06 s against 0.3.2's 0.76 s). (4) is flake.

**Context:** (1) tell `EXECUTE` strings from other strings in `_lex_sql`. (2) list each shape in `ALLOW_SOFTER` with the reason, with corpus cases. (3) see that entry. (4) widen the bound, or measure a ratio as the other linearity tests do.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Never worse than 0.3.2 for time

**What:** `NeverWorseThanMainTests` compares answers only. Add a time check per case: this branch's scan takes at most max(5 x 0.3.2's time, 0.3.2's time + 1 s), median of 3 runs each, honouring `CUSTODY_TIME_SLACK`, with both PR #24 performance repros (512 KB nested Firebase rules; a 400-deep, 9,000-folder `.claude/`) in the corpus.

**Why:** Both PR #24 performance P1s (unbudgeted condition recursion; an O(depth²) never-open MCP walk) passed the answer-only differential test, and a reviewer had to find them. For PR #24, "not worse on time" meant no `partial: true` that 0.3.2 does not also give.

**Context:** needs 0.3.2 runnable in CI (check out `12621fd`'s `custody_scan.py` beside the branch's), and a compact encoding for generated cases, since the repros are too big for `cases.json`'s `{rel: body}` format. The bench script in `HANDOFF-2026-10-01-pr24-false-nothing-found.md` builds every shape. First item of the next custody-check PR.

**Effort:** M
**Priority:** P1
**Depends on:** None

### One work budget per file, and a linear condition parser

**What:** (1) Replace the per-condition recursion budgets (`_rec_budget`, `_charge`) with one work budget per scanned file, owned by the scan loop and passed to every evaluator added since 0.3.2, where running out leads to each check's unevaluated or gap path. (2) Parse a Firebase or SQL condition once into a tree instead of stripping and re-splitting at every level; build the paren levels at C speed (`itertools.accumulate` over a translated string) meanwhile.

**Why:** After the PR #24 fix, conditions are linear but about 20x slower than 0.3.2 on adversarial input (0.57 s against 0.03 s on a 512 KB file of 64-deep groups; 38.7 s against 2.0 s for 70 such files, still under the 120 s deadline). Around 200 such files in one repo would reach the deadline. Agreed stop rule: if another review finds a superlinear path in code this branch added, do (1) rather than another per-function budget.

**Context:** the SQL lexer has the same kind of residual: `_lex_sql` is a per-token Python loop, so after the PR #24 review fixes (lex once per file, C-speed blanking) a string-dense 512 KB migration still takes about 2.6x 0.3.2's time (realistic seed files 1.4x; 420 of them finish in 77 s against 0.3.2's 50 s). A single master regex per token kind would cut it. `_firebase_open`, `_strip_outer_parens`, `_sql_predicate_open` in `custody_scan.py`. The work-count tests in `WorseThanMainPerformanceTests` patch `_strip_outer_parens`; replace them with a budget-level oracle when the parser changes.

**Effort:** M
**Priority:** P2
**Depends on:** None

### One walk per never-open folder, and pruning heavy subtrees

**What:** `count_files` and `_mcp_configs_inside` each walk a never-open agent folder; merge them into one bounded walk. In that walk, skip known heavy subtrees (`node_modules`, `.git`, `worktrees/*`) for the MCP name search, or count them without descending.

**Why:** Each folder now counts toward the 10,000-entry cap twice in the MCP walk (as an entry and as a step), so a `.claude/worktrees/<name>/node_modules` checkout of about 5,000 folders stops the walk and withholds Q1, and mcp-named packages inside it become `mcp-config-not-opened` rows. Measured on 2026-10-02: zero Q1 drift on the owner's nine repos, but a synthetic `.claude/worktrees/x/node_modules` of 6,000 packages moves Q1 from Nothing found (0.3.2) to Don't know. Cautious, not wrong, but noisy.

**Context:** `walk()` in `custody_scan.py`, where `is_never_open_dir` calls both functions. Keep `followlinks=False` and `_lexists_inside`. Also: the MCP walk passes `onerror=lambda e: None`, so an unreadable folder inside a never-open agent folder (`chmod 000 .claude/locked`) is skipped without a Q1 gap; set `truncated` from `onerror` (0.3.2 never walked these folders, so this is not worse than main).

**Effort:** S
**Priority:** P3
**Depends on:** None

### Leftovers from the fresh review of 4b7d615 (2026-10-02)

**What:** Not worse than 0.3.2 in the unsafe direction, deferred under the fix-PR rule. (1) New Don't-knows 0.3.2 never raised: `do /* note */ $$ … $$` and `do '…'` bodies are not read as running SQL; `public-view` rows (5 per file, not capped across files) can push the `table-without-rls` row off the 12-row Q3 list; several gaps (a dropped table, an unclosed quote, a Firebase condition over 400 chars, a drop list too long, a cut-off MCP walk) say Don't know with only the scan-summary row, whose tail "no SQL or security-rules file among them" is wrong for a seed-only app; Supabase's own fix `alter view … set (security_invoker = on)` is not credited, and a permanent `drop table` with no re-create blocks Q3 for good. (2) Every Q3 No now comes from 0.3.2's own patterns, so every open rule the new readers find beyond them is `open-rule-unconfirmed` evidence (Don't know), not a No: `using ((((((true))))))`, a top-level `|| true` in Firebase, `if (true)`, `".write": "true"`, `disable` with long whitespace or an inline comment, a real `disable` on a line where 0.3.2 cut a `--` inside a string. (3) Same as 0.3.2: a Firebase condition is cut at `//` (`== "https://…" || true`), `;` or a map's `}` inside a string; a SQL file whose only rule-like text is a quoted name (`create index "row level security"`) counts as a rule file read. (4) Speed residuals, linear, measured on python 3.9.6: pg_dump-shaped SQL 1.39x 0.3.2 (512 files at the 256 MB cap: 73 s against 53 s), `using ((((((true))))))` repeated 5.9x, `"` + newline repeated 2.8x; the Firebase `\n` lookahead was bounded to 80 spaces (it was 6-9x). Past 60% of the time limit a scan reads SQL and rules files with 0.3.2's readers; that bounds the late work, but a repo where 0.3.2 itself needs nearly the full 120 s can still go partial on this branch first.

**Why:** Each changes an answer or a row in the cautious direction, or matches 0.3.2; a fix PR fixes only what it made worse. (1) is the tester's main complaint (false alarms), so it comes first.

**Context:** (1) `_lex_sql` (`DO_BEFORE_RE`), `resolve()` row order and a named row per gap, `CREATE_VIEW_RE` plus an `ALTER VIEW` reader. (2) Promote one shape at a time from `open-rule-unconfirmed` to a No (`_unconfirmed` in `custody_scan.py`), each in its own PR with corpus cases, an `ALLOW_NEW_NO` reason, and an adversarial pass aimed at that shape alone: three review passes on PR #24 each found new false Nos in these readers (strings, comments, `$` names, COPY data, nested comments, map literals, SQL `||`). (3) `FIREBASE_IF_RE` should end at `;`/`}` only outside strings. (4) `_lex_sql`'s per-token loop, `_sql_predicate_open` caching by group text.

**Effort:** M
**Priority:** P2
**Depends on:** None

### False Nos kept from 0.3.2

**What:** 0.3.2 answers No, wrongly, for (1) `disable row level security` or `using (true)` inside a SQL string or comment string (`comment on table … is 'never disable row level security'`), (2) the same words as a quoted name (`create index "disable row level security"`), (3) Firebase `if true && request.auth != null`, (4) a key in a browser folder in a file with a bare `import "server-only"` (in Next.js the build refuses to bundle it; in Vite it does not), and (5) a disable line after an unbalanced nested comment (`/* avatars/* */ … -- old block ended here */`), which Postgres treats as commented out. 0.3.3 keeps every one of these Nos on purpose.

**Why:** PR #24 changed all five and each change broke a correct No somewhere else (a commented-out `import "server-only"`, a `/* … avatars/* … */` glob). The rule since then: a fix never makes an answer less cautious than the release. Each of these needs its own PR, its own cases in the differential corpus, and a proof that no correct No is lost.

**Context:** the lexer already knows where strings, names and comments are (`_lex_sql`), so (1) and (2) need only the decision; (4) needs framework detection (Next/RSC only) and comment-free matching; (3) needs `&&` evaluated as "depends on auth" rather than open.

**Effort:** M
**Priority:** P2
**Depends on:** None

## Completed

### Q3 "nothing found" from a lone seed.sql

**What:** Any `.sql` file counts as a rule file, so a project whose only SQL is `supabase/seed.sql` (one `insert`) can reach Q3 Nothing found with "1 rule file read".

**Why:** `questions.md` promises that with no rule file the answer stays Don't know because rules live in a dashboard; a seed file is not a rule file. Found by the Claude adversarial pass in the v0.3.0 pre-merge review.

**Context:** `test_nothing_found_is_never_a_no_and_never_on_a_partial_scan` encodes the current rule (`select 1;` in a migration earns Nothing found), so this is a design change, not a bug fix: count a `.sql` file as a rule file only when it holds `create table`, `create policy`, `alter table … row level security` or `storage.buckets`; `.rules` and `database.rules.json` always count. Decide against the workshop corpus.

**Effort:** S
**Priority:** P2
**Depends on:** None

**Completed:** v0.3.3 (2026-09-30)

### Test fixtures use real .env filenames

**What:** `scripts/fixtures/env_names/*/` contain files literally named `.env.production` and `.env.staging`. A tightened agent sandbox that denies reading `~/**/.env*` (a sensible default) makes `copy_fixture` fail with "Operation not permitted", and four tests error for a reason that has nothing to do with the code.

**Why:** The suite should not need the sandbox switched off to run.

**Context:** Hit on 2026-09-22 while scanning a corpus of local apps. Fix by storing the fixtures under a neutral name (`dotenv.production`) and renaming them during `copy_fixture`, so the bytes on disk never match an `.env*` deny rule.

**Effort:** S
**Priority:** P2
**Depends on:** None

**Completed:** v0.2.0 (2026-09-23)
