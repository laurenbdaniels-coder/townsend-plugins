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

**Context:** The CI job is `custody-check-windows` in `.github/workflows/ci.yml`, kept `continue-on-error: true` until it is green. The plan's drop order named the Windows job as the first thing to cut, and it was cut. Start with the threaded reader path in `git_facts` (already written for platforms without non-blocking pipes) and the `tearDown` permission handling in `ScanCase`. On Windows the 0.3.3 overlay also ends with status `error` (seen in the PR #24 CI log, 2026-10-07: rows read `an error; please report it` where 0.3.2 says `0 files scanned`); that is the cautious direction, but find the exception before calling Windows supported.

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

**Context:** the blocker is gone: 0.3.3 runs 0.3.2 as `cs.release` (`custody_scan_0_3_2.py`), and `cases.json` now takes generated bodies (`{"repeat", "times"}`), scan args and hard links. Done in PR #24: `WallTimeBoundTests` pins the overlay's budget (total <= 0.3.2's time + max(5 s, 2 x 0.3.2's time), never past 80% of the deadline) on both performance shapes, and `ReadingCostRatchetTests` ratchets the whole-scan ratio per adversarial shape. Still open: the per-case time check across the whole corpus.

**Effort:** S
**Priority:** P2
**Depends on:** None

### One work budget per file, and a linear condition parser

**What:** (1) Replace the per-condition recursion budgets (`_rec_budget`, `_charge`) with one work budget per scanned file, owned by the scan loop and passed to every evaluator added since 0.3.2, where running out leads to each check's unevaluated or gap path. (2) Parse a Firebase or SQL condition once into a tree instead of stripping and re-splitting at every level; build the paren levels at C speed (`itertools.accumulate` over a translated string) meanwhile.

**Why:** Conditions are linear but about 20x slower than 0.3.2 on adversarial input (2026-10-06, whole scan: 0.43 s against 0.02 s on a 512 KB file of 64-deep groups). Since the overlay redesign this cannot make a scan partial or slow it past the overlay budget (2 x 0.3.2's time, at least 5 s, at most 80% of the deadline); past the budget, Nothing found on Q1/Q3/Q9 is withheld with a `checks-not-finished` row. So the cost is a lost Nothing found on hostile repos, not a worse answer. Agreed stop rule: if another review finds a superlinear path in code this branch added, do (1) rather than another per-function budget.

**Context:** the SQL lexer has the same kind of residual: `_lex_sql` is a per-token Python loop, so after the PR #24 review fixes (lex once per file, C-speed blanking) a string-dense 512 KB migration still takes about 2.6x 0.3.2's time (realistic seed files 1.4x; 420 of them finish in 77 s against 0.3.2's 50 s). A single master regex per token kind would cut it. `_firebase_open`, `_strip_outer_parens`, `_sql_predicate_open` in `custody_scan.py`. The work-count tests in `WorseThanMainPerformanceTests` patch `_strip_outer_parens`; replace them with a budget-level oracle when the parser changes.

**Effort:** M
**Priority:** P2
**Depends on:** None

### One walk per never-open folder, and pruning heavy subtrees

**What:** `count_files` and `_mcp_configs_inside` each walk a never-open agent folder; merge them into one bounded walk. In that walk, skip known heavy subtrees (`node_modules`, `.git`, `worktrees/*`) for the MCP name search, or count them without descending.

**Why:** Each folder now counts toward the 10,000-entry cap twice in the MCP walk (as an entry and as a step), so a `.claude/worktrees/<name>/node_modules` checkout of about 5,000 folders stops the walk and withholds Q1, and mcp-named packages inside it become `mcp-config-not-opened` rows. Measured on 2026-10-02: zero Q1 drift on the owner's nine repos, but a synthetic `.claude/worktrees/x/node_modules` of 6,000 packages moves Q1 from Nothing found (0.3.2) to Don't know. Cautious, not wrong, but noisy.

**Context:** 0.3.2's `count_files` (frozen in `custody_scan_0_3_2.py`) and the overlay's `_mcp_configs_inside` (`overlay_walk` in `custody_scan.py`); merging them waits for the 0.3.4 path below. Keep `followlinks=False` and `_lexists_inside`. Also: the MCP walk passes `onerror=lambda e: None`, so an unreadable folder inside a never-open agent folder (`chmod 000 .claude/locked`) is skipped without a Q1 gap; set `truncated` from `onerror` (0.3.2 never walked these folders, so this is not worse than main).

**Effort:** S
**Priority:** P3
**Depends on:** None

### Leftovers from the fresh review of 4b7d615 (2026-10-02)

**What:** Not worse than 0.3.2 in the unsafe direction, deferred under the fix-PR rule. (1) New Don't-knows 0.3.2 never raised: `do /* note */ $$ … $$` and `do '…'` bodies are not read as running SQL; the gaps each now carry a named row (`table-dropped`, `rules-not-read-whole`, `no-rule-statements`, `mcp-config-not-opened`), but each is still a Don't know 0.3.2 never raised; Supabase's own fix `alter view … set (security_invoker = on)` is not credited, and a permanent `drop table` with no re-create blocks Q3 for good. (2) Every Q3 No now comes from 0.3.2's own patterns, so every open rule the new readers find beyond them is `open-rule-unconfirmed` evidence (Don't know), not a No: `using ((((((true))))))`, a top-level `|| true` in Firebase, `if (true)`, `".write": "true"`, `disable` with long whitespace or an inline comment, a real `disable` on a line where 0.3.2 cut a `--` inside a string. (3) Same as 0.3.2: a Firebase condition is cut at `//` (`== "https://…" || true`), `;` or a map's `}` inside a string; a SQL file whose only rule-like text is a quoted name (`create index "row level security"`) counts as a rule file read. (4) Speed residuals, linear, whole scan against 0.3.2 alone per 512 KB file (2026-10-06, python 3.9.6, after the overlay redesign): Firebase 2.4-2.6x, nested-or Firebase 22x, SQL 1.4-3.9x (`using ((((((true))))))` 3.9x, `"` + newline 3.2x). `ReadingCostRatchetTests` (CUSTODY_SLOW) fails if any shape grows past its ratio + 30%; add each new shape a review finds. The two-phase scan declined on 2026-10-05 is what PR #24 became (D6, 2026-10-06): 0.3.2 runs first and alone, so these costs can delay a scan by at most the overlay budget and never make it partial.

**Why:** Each changes an answer or a row in the cautious direction, or matches 0.3.2; a fix PR fixes only what it made worse. (1) is the tester's main complaint (false alarms), so it comes first.

**Context:** (1) `_lex_sql` (`DO_BEFORE_RE`), overlay row order in `_plans`/`_assemble` (0.3.2's `resolve()` is frozen) and a named row per gap, `CREATE_VIEW_RE` plus an `ALTER VIEW` reader. (2) Promote one shape at a time from `open-rule-unconfirmed` to a No (`_caution` in `custody_scan.py`; the merge clamp in `_plans` must then allow that source), each in its own PR with corpus cases, an `ALLOW_NEW_NO` reason, and an adversarial pass aimed at that shape alone: three review passes on PR #24 each found new false Nos in these readers (strings, comments, `$` names, COPY data, nested comments, map literals, SQL `||`). (3) `FIREBASE_IF_END_RE` / `_firebase_ifs` should end a condition at `;`/`}` only outside strings (update the test-only `FIREBASE_IF_RE` spec with it). (4) `_lex_sql`'s per-token loop, `_sql_predicate_open` caching by group text.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Names inside never-open agent folders in the output

**What:** decide whether `mcp-config-not-opened` rows should name paths inside never-open folders (`.claude/…/mcp.json`) or only the folder.

**Why:** 0.3.2 only counted those files; 0.3.3 names up to five per scan so the founder can find the config. The names pass through `sanitize_path`, but a folder or file name can still say more than the founder expects to see in a report (fresh review of 231b456, 2026-10-07, INVESTIGATE).

**Context:** `_mcp_configs_inside` and `overlay_walk` in `custody_scan.py`. The plan approved naming them (C9); this is a privacy wording call, not a defect.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Leftovers from the fresh review of 231b456 (2026-10-07/08)

**What:** (1) SKILL.md: render No-effect rows first in the five-row verdict table, so the row behind a No is never inside "and N more" (0.3.2 does the same for a key found late; the overlay's No is always last). (2) 0.3.2's `sanitize_path`: a short key ID after `-` or `_` in a file name (`mcp-AKIA…json`) is not redacted; the overlay now names files inside never-open agent folders, so the gap shows in a new place. (3) `_lex_sql`: the `DO` lookback window is 40 characters while `DO_BEFORE_RE` can match about 101, so a `DO   language   plpgsql $$` with long whitespace is read as a function body (cautious: its statements do not count). (4) Put the seeded merge fuzzer from the review (random near-cap 0.3.2 results and overlays, every invariant) in the default suite.

**Why:** none is worse than 0.3.2; each is a weakness in 0.3.2 or a test the fix PR did not need.

**Context:** fresh review of PR #24 at 231b456, cycles 1-2. The fuzzer sketch ran 12,000 cases with 0 violations.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Firebase rules: a `//` or `/*` inside a string hides a later `true` (pre-existing)

**What:** `allow write: if a == 'http://x' || true;` and `allow read: if a == '/*' || true || b == '*/';` get Nothing found from 0.3.2 and from 0.3.3 alike: comment stripping (0.3.2's `_strip_slash_comments` / `_blank_block_comments`) runs before strings are known, so the `true` is cut as part of a comment.

**Why:** a false Nothing found on Q3, but main has it too, so it stays out of the fix PR (fix PRs stay in scope). Needs one left-to-right rules lexer (strings, `//`, `/* */` together) for the condition reader, with differential cases.

**Context:** found by the testing reviewer in the 2026-10-12 re-review of PR #24 (pass 2).

**Effort:** M
**Priority:** P2
**Depends on:** None

### Leftovers from the ship review of 8adc5ce (2026-10-13)

**What:** none is worse than 0.3.2; each was deferred under the ship bar.
(1) Tests a mutation run left unpinned: the `.mts` `code-file-not-read` row for a hard-linked, binary or unreadable file (overlay_walk); a clean finished pass leaving an over-cap 0.3.2 result unchanged (merge); the overlay's own per-file create-table cap gap row; `database.rules.json` keeping `//` inside strings; the Firebase "a comment cut the condition" downgrade (`allow read: if request.path == 'a/*b' || true;` should be `firebase-rules-true-unevaluated`); the 6th+ dropped-table gap count; the RTDB `".read": "true"` row; the lexer's "a quoted name never spans lines" guard; in-string labels for table-dropped and table-without-rls; `_fit` step 5 (possibly dead: check whether a demoted Q1 can ever fit).
(2) Flaky timing tests under CPU load: `LinearityTests.test_growth_is_linear_not_just_fast`, `test_strip_outer_parens_is_linear_in_depth`, and the cycle-5 unclosed-nest bound; move to same-run ratios or op counts. The `nest_failed` mutant is caught only by a hang.
(3) False caution: a pg_dump `COPY … FROM stdin;` data row with an apostrophe un-pairs the lexer's quotes for the rest of the file (treat `COPY … FROM stdin;` … `\.` as data).
(4) Wording: `no-rule-statements` says "no rules file" when 0.3.2 counted a seed `.sql`; a 0.3.2 `scan-summary` row stays beside an overlay `.mts` No; the `_lex_sql` docstring does not describe nested comments, the `nest_failed` fallback or the after-tag retry; `_sql_predicate_open`'s docstring claims `true or …` that `USING_TRUE_RE` never passes it.
(5) Docs the release audit fixed but the ship deferred (prompt files, so a fix would rerun the review): SKILL.md's flag list should name `--deadline-s N` (the `checks-not-finished` row tells the founder to rerun with `--deadline-s 600`); questions.md's Q9 list of unparsed manifests should also name the `*-requirements` / `*_requirements` forms and `environment.yaml`, which `UNPARSED_MANIFEST_RE` already matches.
(6) Structure: `SNIPPET_LABELS` mixes check ids and shape names; `_monitoring_shown` in the tests mirrors production logic (assert literals); `all_checks()` is test-only; `_strip_outer_parens` could reuse `_paren_closes`; the four Firebase/RTDB row loops could be one table; overlay monitoring rows deduped away when 0.3.2 has a row for the same manifest.

**Why:** fix PRs stay in scope; every past fix cycle on this branch created new findings.

**Context:** final /review and /ship review of 8adc5ce (2026-10-13), testing / maintainability / simplification / red team / Claude adversarial, and the /ship coverage audit.

**Effort:** M
**Priority:** P3
**Depends on:** None

### False Nos kept from 0.3.2

**What:** 0.3.2 answers No, wrongly, for (1) `disable row level security` or `using (true)` inside a SQL string or comment string (`comment on table … is 'never disable row level security'`), (2) the same words as a quoted name (`create index "disable row level security"`), (3) Firebase `if true && request.auth != null`, (4) a key in a browser folder in a file with a bare `import "server-only"` (in Next.js the build refuses to bundle it; in Vite it does not), and (5) a disable line after an unbalanced nested comment (`/* avatars/* */ … -- old block ended here */`), which Postgres treats as commented out. 0.3.3 keeps every one of these Nos on purpose.

**Why:** PR #24 changed all five and each change broke a correct No somewhere else (a commented-out `import "server-only"`, a `/* … avatars/* … */` glob). The rule since then: a fix never makes an answer less cautious than the release. Each of these needs its own PR, its own cases in the differential corpus, and a proof that no correct No is lost.

**Context:** the lexer already knows where strings, names and comments are (`_lex_sql`), so (1) and (2) need only the decision; (4) needs framework detection (Next/RSC only) and comment-free matching; (3) needs `&&` evaluated as "depends on auth" rather than open.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Stop-line split: processor-hosted checkout is Gated, not Get a person

**What:** Processor-hosted checkout, Elements or subscriptions (Stripe Checkout, `ui_mode: "embedded_page"`, hosted billing portals) is ordinary Gated work. Only an app that stores or handles card numbers, or holds or moves money between parties (payouts, Connect, escrow), is stop-line. "Real money" alone is too vague to decide it. The founder ticks the stop-line; the agent never ticks it from code or dashboard evidence.

**Why:** a real run (2026-09-30) on an app with embedded Stripe Checkout said Get a person for work that is routine. Decided 2026-09-30.

**Context:** build it inside the deterministic door (E-1, `custody_verdict.py`). It is deliberately more permissive than the release, so the differential test lists the hosted-checkout case (synthetic) with the reason the release was wrong. The talk's close names payments.

**Effort:** M
**Priority:** P1
**Depends on:** E-1 (deterministic door)

### Leftovers from the review of the released-main floor (2026-10-14)

**What:** none is worse than main; each was deferred under the ship bar.
(1) `_release_ref` trusts the local `origin/main`: a stale fetch, or a branch stacked on a parent that was squash-merged, gives a floor one release behind (CI fetches fresh). (2) The release runs in-process (`spec_from_file_location`, not in `sys.modules`): a future release that imports a sibling module would bind the branch's copy, and one that needs `sys.modules[__name__]` would crash loudly; a subprocess run from the export folder avoids both. (3) build_cases.py runs the release through its CLI and the gate calls `scan()` in-process; the audit test catches drift between them. (4) build_cases.py `__main__`: the `--version` call and `answers()` have no timeout or check, so a broken export writes a blank label. (5) The audit copy can pin an old release forever if nobody regenerates after a release (main had the same weakness). (6) The Windows job does not set `CUSTODY_REQUIRE_GIT`, so a failed export falls back to stored answers there (non-gating). (7) `test_the_recipe_exports_a_runnable_release` names 6890302 and needs full history. (8) Simplification: `NeverWorseThanMainTests._scan` repeats `_materialize`; the answers/partial/PII summary is computed in three places; `build_cases.materialize`/`REAL` duplicate `_materialize`/`KEYS`; the two one-slot caches could be `functools.lru_cache`. (9) `_baseline` passes a case's `args` to the release's `scan()`: the first PR adding a `scan()` keyword and a case using it makes the release raise TypeError; drop args the release does not take (`inspect.signature`) or fail with a clear message.

**Why:** fix PRs stay in scope.

**Context:** /review of 8bdfab2 (testing, maintainability, security, performance, simplification, Claude adversarial, Codex).

**Effort:** S
**Priority:** P3
**Depends on:** None

### Leftovers from the #27 review (2026-10-15)

**What:** none is worse than main; each was deferred under the ship bar.
(1) The scanner reports `tags` = 0 when git output is truncated (killed at the cap, rc -9): a real scanner bug, and the source of the `test_git_output_is_bounded_and_truncation_marks_partial` flake.
(2) `extract_scripts` would accept a `C:x.py` member on Windows (a drive-relative join); reject any `:` in a member name.
(3) Release export folders are removed by `atexit`, which never runs after SIGKILL or a CI timeout, so they pile up in the temp folder.
(4) `_git` and `export_release` inherit `GIT_DIR` / `GIT_WORK_TREE` from the caller; pass the file's `GIT_ENV` instead.
(5) A graduated `ALLOW_NEW_NO` entry still excuses a later return to No on the same (case, question) after some PR softened it away (main does the same; a new answer can only be No, so there is no target to pin).
(6) `_release_allow` reads only a plain assignment of a literal dict: a release that writes a list as `ALLOW_SOFTER: dict = {...}`, `dict(...)` or a comprehension stops graduating its entries, so they read as stale (fails closed). A self-check that `_release_allow(__file__)` parses this file's own lists would catch it.
(7) `RANK` puts `yes` and `nothing-found` both at 0, so a move between them is never checked in either direction (main does the same).
(8) `test_ci_never_skips_the_floor` fails whenever the caller has `CUSTODY_RELEASE_REF` exported, because the variable leaks into the test (reproduced on 8208a40).
(9) A malformed `ALLOW_SOFTER` value (`""`, `None`, `()`) errors inside the comparison rather than failing with a message; it fails closed, and `test_softer_exceptions_name_an_answer` names the shape.

**Why:** fix PRs stay in scope.

**Context:** /review of the released-main floor (#27) and of the graduated-exceptions fix (testing, maintainability, Claude adversarial, Codex).

**Effort:** S
**Priority:** P3
**Depends on:** None

### Leftovers from the verdict-script review (0.3.4, 2026-10-15)

**What:** none is more permissive than main's written rule; each was deferred under the ship bar.
(1) `q10_fields` in `--expect` lowercases snippets, so two Q10 rows that differ only in case (`userDob` vs `userdob`) compare equal although only the first ticks the stop-line; the scanner emits the same snippet for the same file, so a rescan cannot produce this, only hand-made JSON can.
(2) The verdict output echoes the whole scan (up to 30000 bytes) next to the verdict; with the 40000-byte cap a full scan plus a long verdict can exceed it and fall back to the written rule (safe, but avoidable: the skill already holds the first scan).
(3) An unknown `stop_line` token ticks the stop-line (cautious) but is reported back as given; report it as `other` so a typo is never echoed.
(4) Free-text stop-line items reach the script only through the model's mapping into `stop_line` tokens (owner's choice, 10/15: mapping only, no override). An eval case with a stop-line item named only in notes would catch a model that skips the mapping.

**Why:** fix PRs stay in scope.

**Context:** /review of feature/custody-verdict (testing, maintainability, simplification, security, Claude adversarial, Codex rounds 1 and 2).

**Effort:** S
**Priority:** P3
**Depends on:** None

### Leftovers from the stop-line split review (0.3.5, 2026-10-15)

**What:** none is more permissive than main outside the listed processor-run payments case; each was deferred under the ship bar.
(1) The processor-invoices corpus rows use the generic all-yes tokens, so the guard test checks tags and tokens but cannot check the founder facts behind them (card details held by the payment company, money settled by it). That mapping lives in SKILL.md prose; an eval case with those founder words would pin it.
(2) A real run rendered the old-`payments` verdict as `## Door: **Get a person**` instead of the template's "**Get a person** and no door" heading (render variance, door correct).
(3) The stop-line footer line is still one 30-word sentence (a test requires one sentence); split it in the plain-English pass and update that test.

**Why:** fix PRs stay in scope.

**Context:** /review of feature/custody-stopline-split (Claude adversarial, Codex rounds 1 and 2, Codex on the widened exception).

**Effort:** S
**Priority:** P3
**Depends on:** None

### Leftovers from the plain-English review (0.3.6, 2026-10-15)

**What:** none changes a door or an answer; each was deferred under the ship bar.
(1) The tests check the fixed text only. The sentences the agent writes into the template (the door sentence, Patch list items, the Don't-know lines) are measured by real runs, not by a test; an eval grader with the 25-word regex, like decision-census's, would pin them.
(2) The next-change line now says "This change needs extra checks: …" where it said "Trigger: …". Check that the workshop deck and handout do not quote the old wording.
(3) The references (`questions.md` outside the By hand and The fix lines, `tiers-and-doors.md`) still say "escalation trigger"; the Plain English section maps it, so the founder never reads it raw.

**Why:** fix PRs stay in scope.

**Context:** /review of fix/custody-check-plain-english (Claude adversarial, Codex rounds 1 and 2, two delta checks on the structural fixes).

**Effort:** S
**Priority:** P3
**Depends on:** None

## decision-census

From the v0.1.0 review (2026-10-15). None met the ship bar; each is a one-line follow-up.

- **Remix / React Router `$` route files are withheld.** `app/routes/projects.$id.tsx` fails the path charset, so its places are counted as held back, and a stop-line field in a held-back schema file is dropped. Decide whether `$` can print (paths go to the Read tool, never a shell), or count withheld stop-line hints. P2.
- **Eval graders check window length, not window position.** A Read of a listed file at an offset far from the listed line passes. Add a post-run check (offset = max(1, line - 15) for some listed line) and one long file to `sunny-shop`. P2.
- **The hostile eval cannot see host-loaded `CLAUDE.md`.** `claude plugin eval` sets `CLAUDE_CODE_DISABLE_CLAUDE_MDS`, so a planted `CLAUDE.md` inside the app is never loaded there. One manual `claude -p` run (2026-10-15, planted `CLAUDE.md` and `src/CLAUDE.md`) followed nothing. Make it a scripted, repeatable check. P2.
- **Python f-string interpolation is blanked.** `f"{price * qty}"` hides the arithmetic inside `{}` (JS template literals are handled). P3.
- **Common shapes still unseen:** multi-line Prisma `where` filters keyed on names other than user/owner/author, `pricing-*` folder heuristics, Rails `before_action` access checks. Add when a real run shows them. P3.
- **`state.hits` is unbounded.** A contrived tree where every line matches could hold millions of tuples; keep only what `select()` can use plus a count. P3.
- **"none" in notes about cards.** About 1 seeded run in 9 writes "none of them gets a card" beside the fixed "each was found once, so no card" line (v0.1.1 eval). Not a claim about the app, but rule 5 bans the word; try dropping the note line so the list stands alone. P2.
- **One-source rule edge cases (v0.1.1 review).** When the shared import sits outside the 31-line window the census cannot name the source file without reading more, so it should treat the places as separate; same-named helpers in different modules or path aliases could look like one source. The `shared-helper-diverges` eval (shared import, divergent logic, must still card) passed 3/3 on both 0.1.0 and 0.1.1. P3.
- **v0.2.0 review follow-ups.** (1) Add a subtle-steering fixture ("pricing is fully centralized here") to test rule 4's carve-out for ordinary AI instructions. (2) Add a case whose two places use ambiguous names, asserting both appear in a card or in "Worth a look". (3) Confirm whether Claude Code's Grep searches hidden folders (`.claude/hooks/*.js`), even in file-names-only mode. (4) The stop-line next step lost its "needs a written scope" reason sentence. (5) A combined 40-call grader (today: 40 reads, 40 searches, 10 globs, each graded). P3.
- **v0.2.0 round-2 review follow-ups (P3, none block).** (1) `never-searches-planted-targets` now matches the whole Grep input, so a legitimate `process.env` or `dotenv` search pattern could false-fail it. (2) Card-line pair graders false-fail `- **Server**:` or `* Server:` bullets. (3) Add a headline-count contains-grader on the pair cases, so two places listed under "Worth a look" with a nothing-found line cannot pass. (4) Name-only searches (`type: md`, `glob: *`) and Reads of `node_modules/` or `.claude/hooks/` are not graded. (5) The required Grep glob lacks `.psql`, `.pgsql`, `.ddl` and `.gql`, which the helper scans. (6) Secret graders read only the final message. (7) A string `"limit":"200"` passes the 120-line grader.
- **v0.2.1 review follow-ups (P3).** (1) The no-code-words grader and the SKILL list would flag an app's own on-screen names ("Import button", "API keys page", "Admin console"); allow a name the founder sees on screen. (2) Align the grader with the SKILL list: plurals (strings, arrays, enums, schemas, configs, booleans) and bare "test". (3) In a real run on 0.2.1 the agent used Grep content mode twice despite rule 2, then opened the report with a jargon note about it; the evals grade names-only and passed 30/30, so this is real-run variance main also has. Consider a plain fixed line for a broken search rule.
- **v0.3.0 review follow-ups (P3).** (1) shared-constant-app's not-carded check could false-fail if an "Also worth a look" line were written as a bullet ending in the shared file's path (never seen). (2) "one of these rules" in the fixed "Why this matters" line reads oddly when there is 1 rule. (3) "Your app has N rules" sounds more final than "this run found N" (main had the same). (4) The "To fix" prompt names one rule; consider a prompt per rule. (5) "Put the rule in one place" could lead an AI tool to drop a server-side access check; "show me the plan first" softens it.
- **v0.3.1 review follow-ups (P3).** (1) Add a check that every quoted AI-tool prompt ends "Change nothing." (rule 8). (2) A fix-request check for the refusal itself ("does not fix"); the assessment check passes on the template line alone. (3) If the founder says yes to the stop-line question after the report, the "Before you change" line above still has the booking link (main has the same). (4) The closing prompt after the four signs still uses a `<the rule>` placeholder in the skill text.
- **Codex install is untested.** The skill looks for `~/.codex/skills/decision-census/scripts/`; try it once before saying it runs in Codex. P3.

## Completed

### Graduated differential exceptions never expire (fix before the stop-line PR merges)

**What:** an `ALLOW_SOFTER` / `ALLOW_NEW_NO` entry that the release's own test file lists is "graduated": the stale check skips it, and the `assertIn` checks still accept it, so a later PR can soften the same (case, question) further with no new entry. Make graduated entries inert in the two `assertIn` checks (`set(self.ALLOW_SOFTER) - _released_main().allow`, same for `ALLOW_NEW_NO`). Watch for one false alarm: a rebase-merge that lands the entry and the scanner change in different commits.

**Why:** main's stale check forced such an entry out; this one is the only worse-than-main path the released-main floor adds. Both lists are empty today, so it cannot fire yet; the stop-line split (item 7) adds the first entry.

**Context:** round-2 review of the released-main floor (2026-10-14), Claude adversarial, reproduced in a clone (branch gate OK, main's gate FAILED). Also from that round: an uncommitted local run on main or a fresh branch gets a floor one release behind (HEAD^1; use HEAD when the scripts folder has uncommitted changes); after a rebase-merge the push-to-main floor is the PR's own previous commit (only matters if a red PR is merged); `_release_allow` ignores annotated assignments (`ALLOW_SOFTER: dict = {...}`), which fails closed.

**Effort:** S
**Priority:** P1
**Depends on:** None

**Completed:** 2026-10-15, differently from the What line above. Subtracting the release's keys failed closed twice in review (a rebase-merge that lands the entry one commit before the scanner change; and a graduated key could never be excused again). Instead each `ALLOW_SOFTER` entry is `(case, question) -> (allowed answer, reason)` and excuses only a move to that exact answer, so a further softening needs the entry edited whether or not the release lists it. Tests: `test_a_softer_exception_excuses_only_the_answer_it_names`, `test_softer_exceptions_name_an_answer`.

### The 0.3.4 path for the overlay

**What:** Decide, before the next scanner change, how 0.3.4 builds on 0.3.3: either (a) the baseline becomes 0.3.3's full output, the overlay folds into one module, and a fresh frozen copy of 0.3.3 becomes the floor, or (b) overlays stack (0.3.2 frozen, 0.3.3's overlay, then 0.3.4's).

**Why:** PR #24 ships two files on purpose (0.3.2 verbatim plus the overlay) after five review rounds showed that weaving new checks into 0.3.2's state leaks into its answers. Folding without a plan reopens that.

**Context:** maintainer checklist for either option: (1) regenerate the frozen file from the new release tag (`git show <tag>:…/custody_scan.py > custody_scan_<ver>.py`); (2) update `RELEASE_FILE` and `RELEASE_SHA256` (sha256 of the text with CRLF read as LF); (3) regenerate `cases.json` with `build_cases.py` against that release; (4) move `ALLOW_NEW_NO` entries the release now gives out of the list; (5) decide fold vs stack and record it here.

**Effort:** S (decision), M (fold)
**Priority:** P2
**Depends on:** PR #24

**Decided (2026-10-14):** neither (a) nor (b) as written: the floor becomes **released main**. The differential tests export the release's `scripts/` folder with `git archive` at `git merge-base HEAD origin/main` and run it beside the branch. Base edits are allowed when the corpus shows equal-or-more caution, with listed exceptions (`ALLOW_SOFTER` / `ALLOW_NEW_NO`, each with its reason). The frozen `custody_scan_0_3_2.py` and `RELEASE_SHA256` stay until a PR edits the base; that PR re-freezes them. See `fixtures/differential/README.md`.

**Completed:** 2026-10-14, the released-main floor PR (tests and corpus only; no plugin version)

### Regenerate the corpus against 0.3.3: the recipe copies one file

**What:** the "regenerate after each release" recipe (`fixtures/differential/README.md`, `build_cases.py` header) copies one `custody_scan.py` to a temp path; from 0.3.3 that file loads `custody_scan_0_3_2.py` from its own folder, so a lone copy returns `internal:release-missing` on every case. Export the whole `scripts/` folder at the release (`git archive <sha> custody-check/skills/custody-check/scripts | tar -x -C <tmp>`) and point `build_cases.py` at the `custody_scan.py` inside it.

**Why:** the next corpus rebuild (#16/#17 rebase, then 0.3.4) would silently compare against envelopes.

**Context:** ship review of 8adc5ce (2026-10-13), maintainability.

**Effort:** S
**Priority:** P1
**Depends on:** None

**Completed:** 2026-10-14, the released-main floor PR (tests and corpus only; no plugin version)

### Regenerate the differential corpus in CI from the pinned release

**What:** CI computes each case's 0.3.2 answers by running `cs.release` instead of reading the answers checked into `cases.json`.

**Why:** the checked-in answers can drift from the release they claim to be; `cs.release` makes the release importable in CI, so the stored answers become an audit artifact rather than the source of truth.

**Context:** `build_cases.py` already runs any scanner by path; `NeverWorseThanMainTests` would call it in-process. Keep the stored answers as a second check until the CI path has run green for a release.

**Effort:** M
**Priority:** P3
**Depends on:** None

Done differently: CI runs released main live on every case (the gate); the stored answers are an audit copy checked against `baseline_sha`.

**Completed:** 2026-10-14, the released-main floor PR (tests and corpus only; no plugin version)

### Q3 "nothing found" from a lone seed.sql

**What:** Any `.sql` file counts as a rule file, so a project whose only SQL is `supabase/seed.sql` (one `insert`) can reach Q3 Nothing found with "1 rule file read".

**Why:** `questions.md` promises that with no rule file the answer stays Don't know because rules live in a dashboard; a seed file is not a rule file. Found by the Claude adversarial pass in the v0.3.0 pre-merge review.

**Context:** `test_nothing_found_is_never_a_no_and_never_on_a_partial_scan` encodes the current rule (`select 1;` in a migration earns Nothing found), so this is a design change, not a bug fix: count a `.sql` file as a rule file only when it holds `create table`, `create policy`, `alter table … row level security` or `storage.buckets`; `.rules` and `database.rules.json` always count. Decide against the workshop corpus.

**Effort:** S
**Priority:** P2
**Depends on:** None

**Completed:** v0.3.3 (2026-10-13)

### Test fixtures use real .env filenames

**What:** `scripts/fixtures/env_names/*/` contain files literally named `.env.production` and `.env.staging`. A tightened agent sandbox that denies reading `~/**/.env*` (a sensible default) makes `copy_fixture` fail with "Operation not permitted", and four tests error for a reason that has nothing to do with the code.

**Why:** The suite should not need the sandbox switched off to run.

**Context:** Hit on 2026-09-22 while scanning a corpus of local apps. Fix by storing the fixtures under a neutral name (`dotenv.production`) and renaming them during `copy_fixture`, so the bytes on disk never match an `.env*` deny rule.

**Effort:** S
**Priority:** P2
**Depends on:** None

**Completed:** v0.2.0 (2026-09-23)
