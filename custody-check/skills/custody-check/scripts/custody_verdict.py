#!/usr/bin/env python3
"""custody-check verdict: the door rule from SKILL.md, applied by a script instead of by the model.

Input: the scanner JSON (it runs custody_scan.py from its own folder, or reads it on stdin for tests), the
founder's answers as fixed tokens, and (0.4.0) what the agent read in the app's code, as fixed tokens too. Output: one
JSON line with the scan, the door, the Patch list order, the stop-line state, per-row render states and the footer's
next step. The script itself reads no file of the app (only the scanner does) and changes nothing.

Read answers (--read) are a third source with a small vocabulary: no on Q1-Q4, yes only on Q2 and Q4, and stop-line
words that only add. Any no wins over a yes from any source; a read yes fills only an answer that is still unknown and
never beats a founder no; a read answer is medium confidence.

It implements SKILL.md's `## Door rule` as written, in order:
  1. stop-line ticked (founder, a stop_line word read from the code, or a Q10 field from the stop-line list) -> Get a person, no door
  2. Q1, Q2 or Q3 is no -> Patch it
  3. partial and Q1 or Q3 still Don't know (or a git-index-unread row on Q1) -> Patch it, never Ship it
  4. two or more of Q4, Q5, Q6, Q9 are no or Don't know -> Patch it
  5. otherwise -> Ship it
Nothing found counts as Don't know everywhere. When this script fails, the skill falls back to the prose rule.

Usage (from the folder that contains the app, after the interview):
  python3 -I custody_verdict.py --repo APP [scanner flags] --answers 'q5_data=no stop_line=none' \
      --read 'q2=yes q4=no' --expect 'q1=no q2=dont-know ... q11=dont-know partial=no'
  python3 -I custody_verdict.py --no-scan --answers '...'      (the scanner could not run at all)
  python3 -I custody_verdict.py --scan-json - --answers '...'  (scanner JSON on stdin; tests)
--expect holds the first scan's answers; a rescan that differs is an error, so the skill uses the first scan.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import types

__version__ = "0.7.1"

HERE = os.path.dirname(os.path.abspath(__file__))
SCANNER = os.path.join(HERE, "custody_scan.py")
QUESTIONS_MD = os.path.join(os.path.dirname(HERE), "references", "questions.md")
SHARED_EXPORTS = ("STOPLINE_FIELDS", "stopline_terms")


def load_shared():
    """Load shared_rules.py (the stop-line list and matcher both free plugins use) from next to this file by path:
    python3 -I keeps this folder off sys.path. Returns (module, None) or (None, error code); no .pyc is written."""
    path = os.path.join(HERE, "shared_rules.py")
    try:
        with open(path, "rb") as fh:
            data = fh.read().replace(b"\r\n", b"\n")
    except FileNotFoundError:
        return None, "internal:shared-missing"
    except OSError:
        return None, "internal:shared-broken"
    module = types.ModuleType("shared_rules")
    module.__file__ = path
    try:
        exec(compile(data, path, "exec"), module.__dict__)
    except Exception:
        return None, "internal:shared-broken"
    if not all(hasattr(module, name) for name in SHARED_EXPORTS):
        return None, "internal:shared-broken"
    return module, None


shared, SHARED_ERROR = load_shared()

QS = ["q%d" % i for i in range(1, 12)]
ANSWERS = ("yes", "no", "dont-know", "nothing-found")
FOUNDER_VALUES = ("yes", "no", "dont-know")
ANSWER_KEYS = tuple(QS) + ("q5_code", "q5_data", "stop_line")
EXPECT_ANSWER_KEYS = tuple("q5_code" if q == "q5" else q for q in QS)
EXPECT_KEYS = EXPECT_ANSWER_KEYS + ("partial", "q10_fields", "git_unread", "stopline_capped")
FIELDS_RE = re.compile(r"^(-|[a-z0-9_-]{1,80}(,[a-z0-9_-]{1,80}){0,63})$")
# 0.3.5 stop-line split: card numbers in the app and money moved between people replace "payments". The old word is
# still accepted and still ticks (an old answers block the founder did not clarify stays on the stop-line).
LEGACY_STOP_LINE_VALUES = ("payments",)
STOP_LINE_VALUES = ("none", "card-numbers", "moves-money", "health", "sensitive", "scale") + LEGACY_STOP_LINE_VALUES
# What reading the code can show (SKILL.md "Read the code"): a key or open rule in code is a no, never proof of a yes
# for Q1/Q3; Q2 and Q4 can be read either way. Stop-line words from the code only add; reading never unticks.
READ_VALUES = {"q1": ("no", "dont-know"), "q2": ("yes", "no", "dont-know"), "q3": ("no", "dont-know"),
               "q4": ("yes", "no", "dont-know")}
READ_STOP_LINE_VALUES = ("card-numbers", "moves-money", "health", "sensitive")
# The stop-line field list and matcher live in shared_rules.py (custody_verdict_test checks SKILL.md rule 6 against it).
MAX_WHERE = 2
SCAN_KEYS = {"ok", "partial", "version", "files_scanned", "stats", "warnings", "git", "questions"}
WARNINGS = {"repo-is-cwd", "repo-contains-cwd"}
SCANNER_BACKED = ("q1", "q3", "q6")  # plus Q5's code half: "Don't know (scanner unavailable)" on the degraded path
MAX_SCAN_BYTES = 30000
MAX_OUTPUT_BYTES = 40000
OUTPUT_KEYS = ("ok", "version", "scanner", "scanner_reason", "scan", "verdict")
RANK = {"no": 0, "dont-know": 1, "nothing-found": 1, "yes": 2}
CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


class UsageError(Exception):
    pass


def unknown(answer):
    return answer in ("dont-know", "nothing-found")


def parse_answers(text):
    """'q1=yes q5_data=no stop_line=card-numbers,health' -> dict. Raises UsageError on anything outside the vocabulary,
    so no free text ever reaches the verdict."""
    out = {}
    for tok in (text or "").split():
        key, sep, val = tok.partition("=")
        if not sep or key not in ANSWER_KEYS + ("q5",):
            raise UsageError("unknown answer key")
        if key == "stop_line":
            vals = val.split(",")
            if not all(re.fullmatch(r"[a-z][a-z_-]{0,31}", v) for v in vals):
                raise UsageError("bad stop_line value")
            val = vals
        elif val not in FOUNDER_VALUES:
            raise UsageError("bad answer value")
        if key in out and out[key] != val:
            raise UsageError("an answer given twice with different values")
        out[key] = val
    if "q5" in out:
        if "q5_code" in out or "q5_data" in out:
            raise UsageError("q5 together with q5_code or q5_data")
        out["q5_code"] = out["q5_data"] = out.pop("q5")
    return out


def parse_read(text):
    """'q2=yes q4=no stop_line=health' -> dict, from READ_VALUES and READ_STOP_LINE_VALUES only."""
    out = {}
    for tok in (text or "").split():
        key, sep, val = tok.partition("=")
        if not sep or key not in tuple(READ_VALUES) + ("stop_line",):
            raise UsageError("unknown read key")
        if key == "stop_line":
            val = val.split(",")
            if not all(v in READ_STOP_LINE_VALUES for v in val):
                raise UsageError("bad read stop_line value")
        elif val not in READ_VALUES[key]:
            raise UsageError("bad read value")
        if key in out and out[key] != val:
            raise UsageError("a read answer given twice with different values")
        out[key] = val
    return out


def parse_expect(text):
    out = {}
    for tok in (text or "").split():
        key, sep, val = tok.partition("=")
        if key in ("partial", "git_unread"):
            ok_val = val in ("yes", "no")
        elif key == "q10_fields":
            ok_val = bool(FIELDS_RE.match(val))
        elif key == "stopline_capped":
            ok_val = val in ("0", "1")
        else:
            ok_val = val in ANSWERS
        if not sep or key not in EXPECT_KEYS or not ok_val or key in out:
            raise UsageError("bad --expect token")
        out[key] = val
    if set(out) != set(EXPECT_KEYS):
        raise UsageError("--expect needs every key")
    return out


def expect_tokens(scan):
    """The --expect string for a scan (what the skill writes from the first scan's JSON): every answer, partial, the
    Q10 snippets lowercased (any other character run becomes `_`), deduplicated and sorted (`-` when there are none), whether Q1 has a git-index-unread
    row, and whether the scanner dropped stop-line rows to fit (stats.stopline_rows_capped above 0). These are everything
    the door reads from the scan, so an equal rescan gives the first scan's door."""
    q = scan["questions"]
    parts = ["%s=%s" % (k, q["q5"]["code"]["answer"] if k == "q5_code" else q[k]["answer"]) for k in EXPECT_ANSWER_KEYS]
    fields = sorted({re.sub(r"[^a-z0-9_-]+", "_", e.get("snippet", "").lower())[:80] or "_" for e in q["q10"]["evidence"]})
    git_unread = any(e.get("check") == "git-index-unread" for e in q["q1"]["evidence"])
    return " ".join(parts + ["partial=%s" % ("yes" if scan["partial"] else "no"),
                             "q10_fields=%s" % (",".join(fields) or "-"),
                             "git_unread=%s" % ("yes" if git_unread else "no"),
                             "stopline_capped=%d" % (1 if _rows_capped(scan) else 0)])


def _rows_capped(scan):
    return scan["stats"].get("stopline_rows_capped", 0) > 0


def known_checks():
    """Every check name in questions.md's "All check names" appendix (the list SKILL.md accepts output against)."""
    with open(QUESTIONS_MD, encoding="utf-8") as fh:
        text = fh.read()
    section = text.split("## All check names", 1)[1].split("\n## ", 1)[0]
    names = set()
    for line in section.splitlines():
        if line.startswith("- **Q"):
            names.update(re.findall(r"`([a-z0-9-]+)`", line))
    return names


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def accept_scan(text):
    """SKILL.md's acceptance rule for the scanner output. Returns (scan, None) or (None, reason)."""
    if text.endswith("\n"):
        text = text[:-1]
    if "\n" in text or not text.startswith("{"):
        return None, "not one JSON line"
    if len(text.encode("utf-8")) > MAX_SCAN_BYTES:
        return None, "over %d bytes" % MAX_SCAN_BYTES
    try:
        scan = json.loads(text)
    except ValueError:
        return None, "not JSON"
    if not isinstance(scan, dict):
        return None, "not an object"
    if scan.get("ok") is False:
        return None, "scanner error"
    if set(scan) != SCAN_KEYS or scan["ok"] is not True:
        return None, "unexpected top-level keys"
    if any(CONTROL.search(s) for s in _strings(scan)):
        return None, "control characters"
    if not isinstance(scan["partial"], bool) or not isinstance(scan["files_scanned"], int) or scan["files_scanned"] < 1:
        return None, "nothing was read"
    if not isinstance(scan["warnings"], list) or not set(scan["warnings"]) <= WARNINGS:
        return None, "unknown warning"
    try:
        checks = known_checks()
    except (OSError, IndexError):
        return None, "check list unreadable"
    qs = scan["questions"]
    if not isinstance(qs, dict) or not all(q in qs for q in QS):
        return None, "missing question"
    for q in QS:
        parts = [qs[q].get("code"), qs[q].get("data")] if q == "q5" and isinstance(qs[q], dict) else [qs[q]]
        for part in parts:
            if not isinstance(part, dict) or part.get("answer") not in ANSWERS or not isinstance(part.get("evidence"), list):
                return None, "bad answer"
            for ev in part["evidence"]:
                if not isinstance(ev, dict) or ev.get("check") not in checks or not isinstance(ev.get("snippet", ""), str):
                    return None, "unknown check"
    if not isinstance(scan["stats"], dict):
        return None, "bad stats"
    capped = scan["stats"].get("stopline_rows_capped", 0)  # 0.6.1; an older scan has none and reads as 0
    if not isinstance(capped, int) or isinstance(capped, bool) or capped < 0:
        return None, "bad stats"
    return scan, None


def stop_line_where(rows, capped):
    """At most two `path:line` places for the extra-risk block, never app text. Rows whose snippet names a stop-line
    term come first: the frozen scanner's before the overlay's (`stopline-field`), and a row that adds a term before
    one that repeats a term. Other Q10 rows fill the rest, except when the scanner capped stop-line rows (then the
    report shows only rows that tick). No ticking row: no places (the founder's answers or the cap alone ticked it)."""
    ticking = [(e, shared.stopline_terms(e.get("snippet", ""))) for e in rows]
    ticking = sorted([x for x in ticking if x[1]], key=lambda x: x[0].get("check") == "stopline-field")
    if not ticking:
        return []
    seen, first, again = set(), [], []
    for e, terms in ticking:
        (first if set(terms) - seen else again).append(e)
        seen.update(terms)
    others = [] if capped else [e for e in rows if not shared.stopline_terms(e.get("snippet", ""))]
    where = []
    for e in first + again + others:
        place = "%s:%s" % (e.get("path", ""), e.get("line", 0))
        if place not in where:
            where.append(place)
    return where[:MAX_WHERE]


def _confidence(founder):
    return "high" if founder in ("yes", "no") else "low"


def _merge(s_ans, s_conf, founder):
    """(answer, source, confidence). SKILL.md: a founder answer fills a scanner Don't know or Nothing found and never
    changes a scanner no; a founder yes on a scanner yes raises it to high. A founder no or Don't know on a scanner yes
    takes the lower answer (the prose is silent there; this is the cautious reading)."""
    if s_ans is None:
        return (founder, "you", _confidence(founder)) if founder else ("dont-know", "none", "low")
    if s_ans == "no" or founder is None:
        return s_ans, "scanner", s_conf
    if unknown(s_ans) or founder != "yes":
        return founder, "you", _confidence(founder)
    return "yes", "scanner", "high"


def _apply_read(row, read):
    """A read answer on top of the scanner+founder row: a no always wins; a yes fills only an unknown."""
    if read == "no" and row["answer"] != "no":
        row.update(answer="no", source="read", confidence="med")
    elif read == "yes" and unknown(row["answer"]):
        row.update(answer="yes", source="read", confidence="med")


def decide(scan, answers, read=None):
    """The verdict. scan is accepted scanner JSON, or None on the degraded path. read is parse_read's dict, or None
    when the agent passed no --read (then the verdict is exactly the released 0.3.6 verdict)."""
    degraded = scan is None
    partial = bool(scan["partial"]) if scan else False
    qs = scan["questions"] if scan else {}
    rows = {}
    for q in QS:
        if q == "q5":
            halves = {}
            for half in ("code", "data"):
                part = qs.get("q5", {}).get(half) if scan else None
                halves[half] = dict(zip(("answer", "source", "confidence"),
                                        _merge(part["answer"] if part else None, part.get("confidence") if part else None,
                                               answers.get("q5_" + half))))
            low = min((halves["code"], halves["data"]), key=lambda h: (RANK[h["answer"]], h["answer"] != "dont-know"))
            rows[q] = dict(low, label=None, code=halves["code"], data=halves["data"])
            if degraded and unknown(halves["code"]["answer"]) and halves["code"]["source"] == "none":
                rows[q]["label"] = "scanner-unavailable"
            continue
        part = qs.get(q) if scan else None
        founder = answers.get(q)
        if partial and q in ("q1", "q3") and unknown(part["answer"]) and founder != "no":
            founder = None  # decided 10/15: a founder yes cannot stand in for files a partial scan never read
        a, src, conf = _merge(part["answer"] if part else None, part.get("confidence") if part else None, founder)
        rows[q] = {"answer": a, "source": src, "confidence": conf, "label": None}
        if read and q in read:
            _apply_read(rows[q], read[q])
        if degraded and q in SCANNER_BACKED and unknown(rows[q]["answer"]) and rows[q]["source"] == "none":
            rows[q]["label"] = "scanner-unavailable"

    git_unread = bool(scan) and any(e.get("check") == "git-index-unread" for e in qs["q1"]["evidence"])
    if git_unread and rows["q1"]["answer"] != "no":
        rows["q1"].update(answer="dont-know", source="scanner", confidence="low", label="git-not-read")
    rerun = partial and (unknown(rows["q1"]["answer"]) or unknown(rows["q3"]["answer"]))
    if partial:
        for q in ("q1", "q3"):
            if unknown(rows[q]["answer"]) and rows[q]["label"] is None:
                rows[q]["label"] = "scan-incomplete"

    founder_sl = list(answers.get("stop_line", []))
    fields = set()
    if scan:
        for e in qs["q10"]["evidence"]:
            fields.update(shared.stopline_terms(e.get("snippet", "")))
    capped = bool(scan) and _rows_capped(scan)
    read_sl = list(read.get("stop_line", [])) if read else []
    ticked = any(v != "none" for v in founder_sl) or bool(fields) or bool(read_sl) or capped

    patch = [q for q in ("q1", "q2", "q3") if rows[q]["answer"] == "no"]
    patch += [q for q in ("q4", "q5", "q6", "q9") if rows[q]["answer"] == "no" or unknown(rows[q]["answer"])]
    failing_four = sum(1 for q in ("q4", "q5", "q6", "q9") if rows[q]["answer"] == "no" or unknown(rows[q]["answer"]))

    if ticked:
        door, step = "get-a-person", "stop-line"
    elif any(rows[q]["answer"] == "no" for q in ("q1", "q2", "q3")):
        door, step = "patch-it", "q1-q2-q3-no"
    elif rerun:
        door, step = "patch-it", "partial-unknown"
    elif git_unread:
        door, step = "patch-it", "git-not-read"
    elif failing_four >= 2:
        door, step = "patch-it", "two-of-q4-q5-q6-q9"
    else:
        door, step = "ship-it", "ship"

    if ticked:
        footer = "stop-line"
    elif degraded:
        footer = "scanner-unavailable"
    elif partial:
        footer = "partial"
    else:
        footer = "default"

    stop_line = {"ticked": ticked, "founder": founder_sl, "fields": sorted(fields),
                 "where": stop_line_where(qs["q10"]["evidence"], capped) if scan else [], "capped": capped}
    if read is not None:
        stop_line["read"] = read_sl
    return {
        "door": door,
        "door_step": step,
        "stop_line": stop_line,
        "rerun_recipe": {"needed": rerun,
                         "max_file_bytes": bool(rerun and scan and scan["stats"].get("files_skipped_oversize_relevant"))},
        "patch_list": patch[:3] if door != "ship-it" else [],
        "patch_list_total": len(patch) if door != "ship-it" else 0,
        "offer_shelve": door != "ship-it" and len(patch) > 3,
        "rows": rows,
        "dont_know": [q for q in QS if unknown(rows[q]["answer"])],
        "footer_next_step": footer,
    }


def run_scanner(args):
    cmd = [sys.executable, "-I", SCANNER, "--repo", args.repo]
    for flag, val in (("--max-files", args.max_files), ("--max-file-bytes", args.max_file_bytes),
                      ("--max-total-bytes", args.max_total_bytes), ("--deadline-s", args.deadline_s)):
        if val is not None:
            cmd += [flag, str(val)]
    for d in args.exclude_dir:
        cmd += ["--exclude-dir", d]
    for p in args.browser_prefix:
        cmd += ["--browser-prefix", p]
    timeout = (args.deadline_s or 120.0) + 60.0
    out = subprocess.run(cmd, cwd=os.getcwd(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, timeout=timeout)
    return out.stdout.decode("utf-8", "replace")


def full_read_plan_id(args):
    """The plan_id full_read_slices.py gives for this app and these flags (0.7.1). The verdict only runs when the
    agent passes the same id, which it can only get by running the full read's step 1; the id changes nothing else."""
    cmd = [sys.executable, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "full_read_slices.py"),
           "--repo", args.repo]
    for flag, val in (("--max-files", args.max_files), ("--max-file-bytes", args.max_file_bytes)):
        if val is not None:
            cmd += [flag, str(val)]
    for d in args.exclude_dir:
        cmd += ["--exclude-dir", d]
    for p in args.browser_prefix:
        cmd += ["--browser-prefix", p]
    out = subprocess.run(cmd, cwd=os.getcwd(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, timeout=(args.deadline_s or 120.0) * 2 + 120.0)
    line = next((l for l in out.stdout.decode("utf-8", "replace").splitlines() if l.startswith("{")), "{}")
    value = json.loads(line).get("plan_id")
    return value if isinstance(value, str) else None


HINTS = {
    "full-read-missing": "the full read has not run for this app: do references/full-read.md now (its step 1 prints "
                         "plan_id), then run the verdict again with --full-read <plan_id>. This is not a failure: "
                         "do not use the written door rule",
    "usage": "the verdict command was not well formed; use the written door rule",
    "scan-failed": "the second scan did not run or was not accepted; use the written door rule on the first scan",
    "scan-changed": "the second scan differed from the first; use the written door rule on the first scan",
    "scan-rejected": "the scanner JSON was not accepted; use the written door rule",
    "internal": "the verdict script hit a bug; use the written door rule",
    "internal:shared-missing": "shared_rules.py is missing next to the verdict script: reinstall the plugin, or re-run "
                               "the cp -R command in README step 1; for now use the written door rule",
    "internal:shared-broken": "shared_rules.py next to the verdict script is damaged: reinstall the plugin, or re-run "
                              "the cp -R command in README step 1; for now use the written door rule",
}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def fail(code):
    emit({"ok": False, "error": code, "hint": HINTS[code]})
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if SHARED_ERROR is not None:
        return fail(SHARED_ERROR)
    try:
        p = _Parser(prog="custody_verdict.py", add_help=False)
        mode = p.add_mutually_exclusive_group(required=True)
        mode.add_argument("--repo")
        mode.add_argument("--no-scan", action="store_true")
        mode.add_argument("--scan-json", choices=["-"])
        p.add_argument("--answers", default="")
        p.add_argument("--read")
        p.add_argument("--expect")
        p.add_argument("--max-files", type=int)
        p.add_argument("--max-file-bytes", type=int)
        p.add_argument("--max-total-bytes", type=int)
        p.add_argument("--deadline-s", type=float)
        p.add_argument("--exclude-dir", action="append", default=[])
        p.add_argument("--browser-prefix", action="append", default=[])
        p.add_argument("--full-read")
        args = p.parse_args(argv)
        answers = parse_answers(args.answers)
        read = parse_read(args.read) if args.read is not None else None
        expect = None
        if args.repo is not None:
            if args.expect is None:
                raise UsageError("--repo needs --expect")
            expect = parse_expect(args.expect)
        elif args.expect is not None:
            raise UsageError("--expect only goes with --repo")
    except UsageError:
        return fail("usage")
    try:
        scan = None
        if args.repo is not None:
            try:
                text = run_scanner(args)
            except (OSError, subprocess.SubprocessError):
                return fail("scan-failed")
            scan, _reason = accept_scan(text)
            if scan is None:
                return fail("scan-failed")
            got = parse_expect(expect_tokens(scan))
            if got != expect:
                return fail("scan-changed")
            try:
                expected_plan = full_read_plan_id(args)
            except (OSError, subprocess.SubprocessError, ValueError):
                expected_plan = None
            if not args.full_read or expected_plan is None or args.full_read != expected_plan:
                return fail("full-read-missing")
        elif args.scan_json:
            scan, _reason = accept_scan(sys.stdin.read())
            if scan is None:
                return fail("scan-rejected")
        verdict = decide(scan, answers, read)
        out = {"ok": True, "version": __version__, "scanner": "ran" if scan else "unavailable",
               "scanner_reason": None if scan else "no-scan", "scan": scan, "verdict": verdict}
        if len(json.dumps(out, ensure_ascii=True, separators=(",", ":"))) > MAX_OUTPUT_BYTES:
            return fail("internal")
        emit(out)
        return 0
    except Exception:  # noqa: BLE001 - one envelope, never a traceback: the skill falls back to the prose rule
        return fail("internal")


if __name__ == "__main__":
    sys.exit(main())
