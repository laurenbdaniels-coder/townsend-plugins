"""Tests for custody_verdict.py: one test per precedence bullet of SKILL.md's door rule, parity with the scanner and
the answers block, the CLI envelope, and the differential corpus (fixtures/verdict/corpus.json), which holds the door
SKILL.md's prose rule gives on realistic scans plus answers, labelled by hand. No door may be more permissive than it.

Run from this folder: python3 -m unittest custody_verdict_test
"""
import copy
import io
import json
import os
import re
import subprocess
import sys
import unittest
from unittest import mock

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VERDICT = os.path.join(SCRIPT_DIR, "custody_verdict.py")
FIXTURES = os.path.join(SCRIPT_DIR, "fixtures")
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

import custody_verdict as cv  # noqa: E402

QS = ["q%d" % i for i in range(1, 12)]
RANK = {"get-a-person": 0, "patch-it": 1, "ship-it": 2}


def row(check, snippet="", path=""):
    return {"path": path, "line": 0, "snippet": snippet, "check": check}


def make_scan(partial=False, files_scanned=40, **answers):
    """A scanner JSON shaped like 0.3.3's. Every question defaults to yes (so the door is Ship it unless a test
    moves it); pass q1="no" etc. A value may be (answer, [rows]) to set the evidence too."""
    stats = {k: 0 for k in ("files_skipped_oversize", "files_skipped_oversize_relevant", "files_skipped_binary",
                            "files_skipped_generated", "files_never_open", "files_skipped_special",
                            "files_skipped_hardlink", "files_errored", "dirs_unreadable", "dirs_truncated",
                            "mcp_capped", "git_index_partial", "output_trimmed")}
    stats.update({"max_files_hit": False, "max_total_bytes_hit": False, "deadline_hit": False,
                  "config": {"exclude_dirs_added": [], "browser_prefixes_added": []}})
    qs = {}
    for q in QS:
        val = answers.get(q, "yes")
        ans, ev = val if isinstance(val, tuple) else (val, [row("scan-summary", "40 files scanned, 0 hits")])
        if q == "q5":
            data = answers.get("q5_data", "dont-know")
            qs[q] = {"code": {"answer": ans, "confidence": "med", "evidence": ev},
                     "data": {"answer": data, "confidence": "low", "evidence": []}}
        else:
            qs[q] = {"answer": ans, "confidence": "med", "evidence": ev}
    return {"ok": True, "partial": partial, "version": "0.3.3", "files_scanned": files_scanned, "stats": stats,
            "warnings": [], "git": {"commits": 3, "tags": 0, "shallow": False, "tracked_env_files": []}, "questions": qs}


def ok_scan(**kw):
    """All yes, Q5 data answered by the founder: Ship it with no answers block beyond q5_data."""
    return make_scan(**kw)


def decide(scan, answers="", expect=None):
    return cv.decide(scan, cv.parse_answers(answers))


class DoorPrecedenceTests(unittest.TestCase):
    """One test per bullet of SKILL.md `## Door rule`, in its order."""

    def test_all_yes_is_ship(self):
        v = decide(ok_scan(), "q5_data=yes")
        self.assertEqual(v["door"], "ship-it")
        self.assertEqual(v["door_step"], "ship")
        self.assertEqual(v["patch_list"], [])

    # 1. stop-line
    def test_founder_stop_line_is_get_a_person(self):
        v = decide(ok_scan(), "q5_data=yes stop_line=payments")
        self.assertEqual(v["door"], "get-a-person")
        self.assertEqual(v["stop_line"]["founder"], ["payments"])
        self.assertTrue(v["stop_line"]["ticked"])

    def test_stop_line_none_is_not_ticked(self):
        v = decide(ok_scan(), "q5_data=yes stop_line=none")
        self.assertFalse(v["stop_line"]["ticked"])
        self.assertEqual(v["door"], "ship-it")

    def test_none_with_another_value_is_ticked(self):
        self.assertEqual(decide(ok_scan(), "q5_data=yes stop_line=none,health")["door"], "get-a-person")

    def test_unknown_stop_line_value_counts_as_ticked(self):
        self.assertEqual(decide(ok_scan(), "q5_data=yes stop_line=children")["door"], "get-a-person")

    def test_q10_stop_line_field_is_get_a_person(self):
        for snippet in ("ssn", "dob", "date_of_birth", "dateOfBirth", "birthDate", "card_number", "cardNumber",
                        "creditCard", "user_ssn_last4", "IBAN", "passport_no", "medical_notes", "diagnosis",
                        "social_security_number", "cc_number", "credit_card"):
            scan = ok_scan(q10=("dont-know", [row("pii-field", "email"), row("pii-field", snippet, "prisma/schema.prisma")]))
            v = decide(scan, "q5_data=yes stop_line=none")
            self.assertEqual(v["door"], "get-a-person", snippet)
            self.assertTrue(v["stop_line"]["fields"], snippet)

    def test_q10_ordinary_fields_do_not_tick(self):
        for snippet in ("email", "phone", "address", "salary", "adobe_id", "doberman", "ibanez"):
            scan = ok_scan(q10=("dont-know", [row("pii-field", snippet)]))
            v = decide(scan, "q5_data=yes stop_line=none")
            self.assertFalse(v["stop_line"]["ticked"], snippet)

    def test_q10_fields_never_echo_app_text(self):
        scan = ok_scan(q10=("dont-know", [row("pii-field", "hunter2_dateOfBirth")]))
        v = decide(scan, "q5_data=yes")
        self.assertEqual(v["stop_line"]["fields"], ["date_of_birth"])
        self.assertNotIn("hunter2", json.dumps(v))

    def test_stop_line_beats_q1_no(self):
        self.assertEqual(decide(ok_scan(q1="no"), "q5_data=yes stop_line=scale")["door"], "get-a-person")

    # 2. Q1, Q2 or Q3 no
    def test_q1_no_is_patch(self):
        v = decide(ok_scan(q1="no"), "q5_data=yes")
        self.assertEqual((v["door"], v["door_step"]), ("patch-it", "q1-q2-q3-no"))
        self.assertEqual(v["patch_list"], ["q1"])

    def test_q2_no_is_patch(self):
        self.assertEqual(decide(ok_scan(q2="dont-know"), "q5_data=yes q2=no")["door"], "patch-it")

    def test_q3_no_is_patch(self):
        self.assertEqual(decide(ok_scan(q3="no"), "q5_data=yes")["door"], "patch-it")

    # 3. partial with Q1 or Q3 still Don't know
    def test_partial_q1_dont_know_is_patch_with_rerun(self):
        v = decide(ok_scan(partial=True, q1="dont-know"), "q5_data=yes")
        self.assertEqual((v["door"], v["door_step"]), ("patch-it", "partial-unknown"))
        self.assertTrue(v["rerun_recipe"]["needed"])
        self.assertFalse(v["rerun_recipe"]["max_file_bytes"])
        self.assertEqual(v["rows"]["q1"]["label"], "scan-incomplete")

    def test_partial_q3_dont_know_is_patch(self):
        v = decide(ok_scan(partial=True, q3="dont-know"), "q5_data=yes")
        self.assertEqual(v["door"], "patch-it")
        self.assertEqual(v["rows"]["q3"]["label"], "scan-incomplete")

    def test_rerun_recipe_names_max_file_bytes_when_relevant_files_were_skipped(self):
        scan = ok_scan(partial=True, q1="dont-know")
        scan["stats"]["files_skipped_oversize_relevant"] = 2
        self.assertTrue(decide(scan, "q5_data=yes")["rerun_recipe"]["max_file_bytes"])

    def test_partial_founder_yes_cannot_settle_q1_or_q3(self):
        """Stricter than the 'still Don't know' reading (decided 10/15, listed in ALLOW_STRICTER): on a partial
        scan the founder's yes cannot stand in for files the scanner never read."""
        for q in ("q1", "q3"):
            for gap in ("dont-know", "nothing-found"):
                v = decide(ok_scan(partial=True, **{q: gap}), "q5_data=yes %s=yes" % q)
                self.assertEqual((v["door"], v["door_step"]), ("patch-it", "partial-unknown"), (q, gap))
                self.assertTrue(v["rerun_recipe"]["needed"])
                self.assertEqual((v["rows"][q]["answer"], v["rows"][q]["label"]), (gap, "scan-incomplete"))

    def test_partial_founder_no_on_q1_still_counts(self):
        v = decide(ok_scan(partial=True, q1="dont-know"), "q5_data=yes q1=no")
        self.assertEqual((v["door"], v["door_step"]), ("patch-it", "q1-q2-q3-no"))

    def test_not_partial_founder_yes_fills_q1(self):
        self.assertEqual(decide(ok_scan(q1="dont-know"), "q5_data=yes q1=yes")["door"], "ship-it")

    def test_partial_patch_it_with_empty_patch_list_still_has_the_rerun_recipe(self):
        v = decide(ok_scan(partial=True, q1="dont-know"), "q5_data=yes")
        self.assertEqual((v["door"], v["patch_list"]), ("patch-it", []))
        self.assertTrue(v["rerun_recipe"]["needed"])

    def test_partial_with_q1_and_q3_answered_by_scanner_is_not_this_step(self):
        self.assertEqual(decide(ok_scan(partial=True), "q5_data=yes")["door"], "ship-it")

    def test_git_index_unread_is_never_ship_even_with_founder_yes(self):
        scan = ok_scan(partial=True, q1=("dont-know", [row("git-index-unread", "git's file index was not read")]))
        v = decide(scan, "q5_data=yes q1=yes")
        self.assertEqual(v["door"], "patch-it")
        self.assertEqual(v["rows"]["q1"]["answer"], "dont-know")
        self.assertEqual(v["rows"]["q1"]["label"], "git-not-read")

    def test_git_index_unread_never_ship_when_scan_not_marked_partial(self):
        scan = ok_scan(q1=("dont-know", [row("git-index-unread", "x")]))
        v = decide(scan, "q5_data=yes q1=yes")
        self.assertEqual((v["door"], v["door_step"]), ("patch-it", "git-not-read"))

    # 4. two or more of Q4, Q5, Q6, Q9
    def test_two_of_q4_q5_q6_q9_is_patch(self):
        v = decide(ok_scan(q4="dont-know", q9="no"), "q5_data=yes")
        self.assertEqual((v["door"], v["door_step"]), ("patch-it", "two-of-q4-q5-q6-q9"))
        self.assertEqual(v["patch_list"], ["q4", "q9"])

    def test_one_of_q4_q5_q6_q9_is_ship(self):
        v = decide(ok_scan(q6="no"), "q5_data=yes")
        self.assertEqual(v["door"], "ship-it")
        self.assertEqual(v["patch_list"], [])

    def test_q5_data_dont_know_counts(self):
        """The Q5 data half is Don't know until the founder answers it, so Q5 alone fails."""
        self.assertEqual(decide(ok_scan(q4="dont-know"))["door"], "patch-it")

    # Nothing found = Don't know everywhere
    def test_nothing_found_counts_in_partial_step(self):
        v = decide(ok_scan(partial=True, q3="nothing-found"), "q5_data=yes")
        self.assertEqual(v["door"], "patch-it")
        self.assertEqual(v["rows"]["q3"]["label"], "scan-incomplete")

    def test_nothing_found_counts_in_two_of_four(self):
        self.assertEqual(decide(ok_scan(q9="nothing-found", q4="dont-know"), "q5_data=yes")["door"], "patch-it")

    def test_nothing_found_goes_in_patch_list(self):
        v = decide(ok_scan(q1="no", q9="nothing-found"), "q5_data=yes")
        self.assertEqual(v["patch_list"], ["q1", "q9"])

    def test_nothing_found_goes_on_dont_know_list(self):
        v = decide(ok_scan(q1="nothing-found"), "q5_data=yes")
        self.assertIn("q1", v["dont_know"])

    # Patch list and Shelve
    def test_patch_list_order_and_cap(self):
        v = decide(ok_scan(q1="no", q3="no", q4="no", q6="dont-know", q9="no"), "q5_data=yes")
        self.assertEqual(v["patch_list"], ["q1", "q3", "q4"])
        self.assertEqual(v["patch_list_total"], 5)
        self.assertTrue(v["offer_shelve"])

    def test_three_items_does_not_offer_shelve(self):
        v = decide(ok_scan(q1="no", q4="no", q9="no"), "q5_data=yes")
        self.assertEqual(v["patch_list_total"], 3)
        self.assertFalse(v["offer_shelve"])

    def test_q1_q2_q3_dont_know_is_not_a_patch_item(self):
        v = decide(ok_scan(q1="dont-know", q4="no", q9="no"), "q5_data=yes")
        self.assertEqual(v["patch_list"], ["q4", "q9"])

    # Footer next step, first match wins
    def test_footer_stop_line_first(self):
        v = cv.decide(None, cv.parse_answers("stop_line=health"))
        self.assertEqual(v["footer_next_step"], "stop-line")

    def test_footer_scanner_unavailable_second(self):
        v = cv.decide(None, cv.parse_answers("stop_line=none"))
        self.assertEqual(v["footer_next_step"], "scanner-unavailable")

    def test_footer_partial_third(self):
        self.assertEqual(decide(ok_scan(partial=True), "q5_data=yes")["footer_next_step"], "partial")

    def test_footer_default(self):
        self.assertEqual(decide(ok_scan(), "q5_data=yes")["footer_next_step"], "default")


class AnswerMergeTests(unittest.TestCase):
    """SKILL.md `## Founder answers` and `## Answer rules`."""

    def test_founder_never_changes_a_scanner_no(self):
        v = decide(ok_scan(q3="no"), "q5_data=yes q3=yes")
        self.assertEqual(v["rows"]["q3"]["answer"], "no")
        self.assertEqual(v["rows"]["q3"]["source"], "scanner")
        self.assertEqual(v["door"], "patch-it")

    def test_founder_fills_dont_know_and_nothing_found(self):
        v = decide(ok_scan(q4="dont-know", q9="nothing-found"), "q5_data=yes q4=yes q9=yes")
        self.assertEqual((v["rows"]["q4"]["answer"], v["rows"]["q4"]["source"], v["rows"]["q4"]["confidence"]), ("yes", "you", "high"))
        self.assertEqual(v["rows"]["q9"]["answer"], "yes")
        self.assertEqual(v["door"], "ship-it")

    def test_founder_yes_on_scanner_yes_raises_confidence(self):
        v = decide(ok_scan(), "q5_data=yes q6=yes")
        self.assertEqual((v["rows"]["q6"]["answer"], v["rows"]["q6"]["confidence"]), ("yes", "high"))

    def test_founder_no_on_scanner_yes_takes_the_lower(self):
        """Deliberately stricter than the prose, which is silent here (ALLOW_STRICTER lists it)."""
        v = decide(ok_scan(), "q5_data=yes q6=no q9=dont-know")
        self.assertEqual(v["rows"]["q6"]["answer"], "no")
        self.assertEqual(v["door"], "patch-it")

    def test_q5_is_the_lower_half(self):
        v = decide(ok_scan(), "q5_data=no")
        self.assertEqual(v["rows"]["q5"]["answer"], "no")
        self.assertEqual(v["rows"]["q5"]["code"]["answer"], "yes")
        self.assertEqual(v["rows"]["q5"]["data"]["answer"], "no")

    def test_q5_fills_both_halves(self):
        v = decide(ok_scan(q5="dont-know"), "q5=yes")
        self.assertEqual(v["rows"]["q5"]["answer"], "yes")

    def test_degraded_scanner_questions_start_dont_know(self):
        v = cv.decide(None, cv.parse_answers("q2=yes q4=yes q5_code=yes q5_data=yes q6=yes q9=yes stop_line=none"))
        self.assertEqual(v["rows"]["q1"]["answer"], "dont-know")
        self.assertEqual(v["rows"]["q1"]["label"], "scanner-unavailable")
        self.assertEqual(v["rows"]["q3"]["label"], "scanner-unavailable")
        # The prose rule on the degraded path: no partial flag, Q1/Q3 Don't know do not decide, so Ship it.
        self.assertEqual(v["door"], "ship-it")

    def test_degraded_founder_answers_fill_everything(self):
        v = cv.decide(None, cv.parse_answers("q1=no stop_line=none"))
        self.assertEqual((v["rows"]["q1"]["answer"], v["rows"]["q1"]["source"]), ("no", "you"))
        self.assertEqual(v["door"], "patch-it")


class ExpectTests(unittest.TestCase):
    """--expect pins what the door reads from the first scan: every answer, partial, the Q10 field names and the
    git-index-unread row. A rescan that differs in any of them is scan-changed, so the skill uses the first scan."""

    def run_main(self, first, second, answers="stop_line=none q1=yes q2=yes q3=yes q4=yes q5=yes q6=yes q9=yes"):
        buf = io.StringIO()
        with mock.patch.object(cv, "run_scanner", return_value=json.dumps(second) + "\n"), mock.patch("sys.stdout", buf):
            cv.main(["--repo", "app", "--answers", answers, "--expect", cv.expect_tokens(first)])
        return json.loads(buf.getvalue())

    def test_rescan_that_loses_a_q10_field_is_scan_changed(self):
        """Codex round 1: the first scan shows ssn, a deadline-limited rescan does not; main's prose says Get a person."""
        first = ok_scan(q10=("dont-know", [row("pii-field", "ssn")]))
        second = ok_scan(q10=("dont-know", []))
        out = self.run_main(first, second)
        self.assertEqual((out["ok"], out["error"]), (False, "scan-changed"))

    def test_rescan_that_swaps_a_q10_field_is_scan_changed(self):
        first = ok_scan(q10=("dont-know", [row("pii-field", "email"), row("pii-field", "dob")]))
        second = ok_scan(q10=("dont-know", [row("pii-field", "email"), row("pii-field", "phone")]))
        self.assertEqual(self.run_main(first, second)["error"], "scan-changed")

    def test_rescan_that_loses_git_index_unread_is_scan_changed(self):
        first = ok_scan(q1=("dont-know", [row("git-index-unread", "x")]))
        second = ok_scan(q1=("dont-know", [row("scan-summary", "x")]))
        self.assertEqual(self.run_main(first, second)["error"], "scan-changed")

    def test_same_rescan_gives_a_verdict(self):
        first = ok_scan(q10=("dont-know", [row("pii-field", "dateOfBirth"), row("pii-field", "email"),
                                           row("pii-form-input", "email")]))
        out = self.run_main(first, copy.deepcopy(first))
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["verdict"]["door"], "get-a-person")

    def test_expect_tokens_format(self):
        scan = ok_scan(q1=("dont-know", [row("git-index-unread", "x")]),
                       q10=("dont-know", [row("pii-field", "Email"), row("pii-field", "dob"), row("pii-field", "email")]))
        toks = cv.expect_tokens(scan).split()
        self.assertIn("q10_fields=dob,email", toks)
        self.assertIn("git_unread=yes", toks)
        self.assertIn("q10_fields=-", cv.expect_tokens(ok_scan(q10=("nothing-found", []))).split())
        self.assertIn("git_unread=no", cv.expect_tokens(ok_scan()).split())

    def test_bad_expect_tokens(self):
        good = cv.expect_tokens(ok_scan(q10=("nothing-found", [])))
        cv.parse_expect(good)
        for bad in (good.replace("q10_fields=-", "q10_fields=a;b"), good.replace("q10_fields=-", "q10_fields="),
                    good.replace("git_unread=no", "git_unread=maybe"), good.replace(" git_unread=no", ""),
                    good.replace(" q10_fields=-", "")):
            with self.assertRaises(cv.UsageError, msg=bad):
                cv.parse_expect(bad)


class ParseTests(unittest.TestCase):
    def test_tokens(self):
        a = cv.parse_answers("q1=yes  q5_data=dont-know stop_line=payments,health")
        self.assertEqual(a["q1"], "yes")
        self.assertEqual(a["stop_line"], ["payments", "health"])

    def test_bad_tokens_raise(self):
        for bad in ("q12=yes", "q1=maybe", "q1", "q1=yes q1=no", "q5=yes q5_code=no", "notes=hi", "stop_line=",
                    "stop_line=pay;rm", "q1=nothing-found"):
            with self.assertRaises(cv.UsageError, msg=bad):
                cv.parse_answers(bad)

    def test_stop_line_split_words(self):
        """0.3.5: card numbers and money between people are their own words, and each ticks."""
        self.assertEqual(cv.parse_answers("stop_line=card-numbers,moves-money")["stop_line"], ["card-numbers", "moves-money"])
        for word in ("card-numbers", "moves-money", "health", "sensitive", "scale"):
            self.assertEqual(decide(ok_scan(), "q5_data=yes stop_line=" + word)["door"], "get-a-person", word)

    def test_legacy_payments_still_ticks(self):
        """An old block's "payments" the founder did not clarify stays on the stop-line, as on main."""
        self.assertIn("payments", cv.LEGACY_STOP_LINE_VALUES)
        self.assertEqual(decide(ok_scan(), "q5_data=yes stop_line=payments")["door"], "get-a-person")

    def test_repeat_with_same_value_is_fine(self):
        self.assertEqual(cv.parse_answers("q1=yes q1=yes")["q1"], "yes")


class AcceptScanTests(unittest.TestCase):
    def line(self, scan):
        return json.dumps(scan, separators=(",", ":")) + "\n"

    def test_good_scan(self):
        scan, reason = cv.accept_scan(self.line(ok_scan()))
        self.assertIsNotNone(scan)
        self.assertIsNone(reason)

    def test_rejections(self):
        bad = []
        s = ok_scan(); s["extra"] = 1; bad.append(("keys", self.line(s)))
        s = ok_scan(); s["questions"]["q1"]["answer"] = "maybe"; bad.append(("answer", self.line(s)))
        s = ok_scan(); s["questions"]["q1"]["evidence"] = [row("made-up-check")]; bad.append(("check", self.line(s)))
        s = ok_scan(); s["warnings"] = ["other"]; bad.append(("warning", self.line(s)))
        s = ok_scan(); s["questions"]["q1"]["evidence"] = [row("scan-summary", "a\x07b")]; bad.append(("control", self.line(s)))
        s = ok_scan(files_scanned=0); bad.append(("zero files", self.line(s)))
        bad.append(("two lines", self.line(ok_scan()) + self.line(ok_scan())))
        bad.append(("not json", "{nope\n"))
        bad.append(("too big", self.line(ok_scan(q2=("dont-know", [row("api-route-dir", "x" * 31000)])))))
        bad.append(("envelope", '{"ok":false,"error":"repo-not-found","hint":"h","docs":"d","partial":false}\n'))
        s = ok_scan(); del s["questions"]["q7"]; bad.append(("missing question", self.line(s)))
        for name, text in bad:
            scan, reason = cv.accept_scan(text)
            self.assertIsNone(scan, name)
            self.assertTrue(reason, name)

    def test_every_corpus_scan_is_accepted(self):
        with open(os.path.join(FIXTURES, "verdict", "corpus.json"), encoding="utf-8") as fh:
            scans = json.load(fh)["scans"]
        for name, scan in scans.items():
            if scan is not None:
                self.assertIsNotNone(cv.accept_scan(self.line(scan))[0], name)

    def test_size_reason_names_the_limit(self):
        _, reason = cv.accept_scan(self.line(ok_scan(q2=("dont-know", [row("api-route-dir", "x" * 31000)]))))
        self.assertIn(str(cv.MAX_SCAN_BYTES), reason)

    def test_every_error_hint_points_at_the_written_rule(self):
        for code, hint in cv.HINTS.items():
            self.assertIn("written door rule", hint, code)

    def test_ignores_unknown_fields_inside(self):
        s = ok_scan(); s["questions"]["q1"]["new_field"] = 1
        self.assertIsNotNone(cv.accept_scan(self.line(s))[0])


class ParityTests(unittest.TestCase):
    def test_stop_line_fields_match_scanner(self):
        import custody_scan as cs
        self.assertEqual(set(cv.STOPLINE_FIELDS), set(cs.release.STOPLINE_FIELDS))

    def test_stop_line_fields_match_skill_rule_6(self):
        with open(os.path.join(SKILL_DIR, "SKILL.md"), encoding="utf-8") as fh:
            rule6 = next(l for l in fh if l.startswith("6. **Stop-line.**"))
        self.assertEqual(set(re.findall(r"`([a-z_]+)`", rule6)), set(cv.STOPLINE_FIELDS))

    def test_answer_keys_match_the_example_block(self):
        with open(os.path.join(SKILL_DIR, "assets", "founder-answers-example.md"), encoding="utf-8") as fh:
            text = fh.read()
        keys = set(re.findall(r"^(q\d+(?:_code|_data)?|stop_line):", text, re.M))
        self.assertTrue(keys <= set(cv.ANSWER_KEYS), keys - set(cv.ANSWER_KEYS))
        values = set(re.search(r"comma-separated from (.*)\.", text).group(1).replace("`", "").replace(" ", "").split(","))
        self.assertEqual(values, set(cv.STOP_LINE_VALUES) - set(cv.LEGACY_STOP_LINE_VALUES))

    def test_version_matches_scanner_and_plugin(self):
        import custody_scan as cs
        with open(os.path.join(os.path.dirname(os.path.dirname(SKILL_DIR)), ".claude-plugin", "plugin.json"),
                  encoding="utf-8") as fh:
            plugin = json.load(fh)["version"]
        self.assertEqual({cv.__version__, cs.__version__, plugin}, {plugin})

    def test_skill_maps_stop_line_words_into_tokens(self):
        """Round 1 blocker: free text never reaches the script, so SKILL.md must turn any stop-line item the founder
        names anywhere (notes, stores, users, next_change, the interview) into stop_line tokens."""
        with open(os.path.join(SKILL_DIR, "SKILL.md"), encoding="utf-8") as fh:
            text = fh.read()
        section = text.split("## Run the verdict", 1)[1].split("\n## ", 1)[0]
        for word in ("notes", "stores", "users", "next_change", "interview", "stop_line"):
            self.assertIn(word, section, word)
        self.assertRegex(section, r"(?i)anywhere")
        self.assertRegex(section, r"(?i)children")

    def _run_the_verdict(self):
        with open(os.path.join(SKILL_DIR, "SKILL.md"), encoding="utf-8") as fh:
            text = fh.read()
        return text, text.split("## Run the verdict", 1)[1].split("\n## ", 1)[0]

    def test_skill_lists_the_stop_line_words(self):
        _, section = self._run_the_verdict()
        for word in set(cv.STOP_LINE_VALUES):
            self.assertIn("`%s`" % word, section, word)

    def test_hosted_checkout_maps_to_no_stop_line_word(self):
        """The stop-line split: checkout hosted by the payment company makes the change Gated, never a stop_line word."""
        text, section = self._run_the_verdict()
        sentence = next((x for x in re.split(r"(?<=[.;])\s+", section) if re.search(r"(?i)hosted", x)), "")
        self.assertRegex(sentence, r"(?i)no `stop_line` (word|token)")
        rule6 = next(l for l in text.splitlines() if l.startswith("6. **Stop-line.**"))
        self.assertRegex(rule6, r"(?i)card numbers")
        self.assertRegex(rule6, r"(?i)between people")
        self.assertRegex(rule6, r"(?i)hosted .*Gated")
        self.assertNotRegex(rule6, r"(?i)real money|payments or card details")

    def test_legacy_payments_gets_one_question_of_at_most_25_words(self):
        _, section = self._run_the_verdict()
        m = re.search(r"`payments`[^\n]*?ask[^\n]*?: \"([^\"]+)\"", section)
        self.assertTrue(m, "the legacy-payments follow-up question is not in Run the verdict")
        for sentence in re.split(r"(?<=[.?])\s+", m.group(1)):
            self.assertLessEqual(len(sentence.split()), 25, sentence)

    def test_check_names_are_read_from_questions_md(self):
        names = cv.known_checks()
        for c in ("git-index-unread", "pii-field", "scan-summary", "nothing-found-keys", "checks-not-finished"):
            self.assertIn(c, names)


class CliTests(unittest.TestCase):
    def run_cli(self, args, stdin=None, cwd=FIXTURES):
        out = subprocess.run([sys.executable, "-I", VERDICT] + args, input=stdin, cwd=cwd, capture_output=True,
                             text=True, timeout=300)
        lines = out.stdout.splitlines()
        self.assertEqual(len(lines), 1, out.stdout + out.stderr)
        return json.loads(lines[0])

    def test_end_to_end_on_seeded_app(self):
        first = json.loads(subprocess.run([sys.executable, "-I", os.path.join(SCRIPT_DIR, "custody_scan.py"), "--repo",
                                           "seeded-app"], cwd=FIXTURES, capture_output=True, text=True, timeout=300).stdout)
        out = self.run_cli(["--repo", "seeded-app", "--answers", "stop_line=none", "--expect", cv.expect_tokens(first)])
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["scanner"], "ran")
        self.assertEqual(out["verdict"]["door"], "get-a-person")  # Q10 has ssn and dob
        self.assertEqual(out["verdict"]["stop_line"]["fields"], ["dob", "ssn"])
        self.assertEqual(out["scan"]["questions"]["q3"]["answer"], "no")
        self.assertEqual(sorted(out), sorted(cv.OUTPUT_KEYS))
        self.assertLessEqual(len(json.dumps(out, separators=(",", ":"))), cv.MAX_OUTPUT_BYTES)

    def test_repo_requires_expect(self):
        out = self.run_cli(["--repo", "seeded-app", "--answers", "stop_line=none"])
        self.assertEqual((out["ok"], out["error"]), (False, "usage"))

    def test_a_rescan_that_differs_from_the_first_is_an_error(self):
        first = json.loads(subprocess.run([sys.executable, "-I", os.path.join(SCRIPT_DIR, "custody_scan.py"), "--repo",
                                           "seeded-app"], cwd=FIXTURES, capture_output=True, text=True, timeout=300).stdout)
        first["questions"]["q3"]["answer"] = "nothing-found"
        out = self.run_cli(["--repo", "seeded-app", "--answers", "stop_line=none", "--expect", cv.expect_tokens(first)])
        self.assertEqual((out["ok"], out["error"]), (False, "scan-changed"))

    def test_failed_rescan_is_an_error_not_a_degraded_verdict(self):
        """A rescan that fails must not quietly become the degraded path: the first scan may have had a No."""
        out = self.run_cli(["--repo", "no-such-app", "--answers", "stop_line=none", "--expect", cv.expect_tokens(make_scan())])
        self.assertEqual((out["ok"], out["error"]), (False, "scan-failed"))

    def test_no_scan(self):
        out = self.run_cli(["--no-scan", "--answers", "q1=no stop_line=none"])
        self.assertTrue(out["ok"])
        self.assertEqual(out["scanner"], "unavailable")
        self.assertIsNone(out["scan"])
        self.assertEqual(out["verdict"]["door"], "patch-it")

    def test_scan_json_on_stdin(self):
        out = self.run_cli(["--scan-json", "-", "--answers", "q5_data=yes"], stdin=json.dumps(ok_scan()) + "\n")
        self.assertEqual(out["verdict"]["door"], "ship-it")

    def test_rejected_stdin_scan_is_an_error(self):
        out = self.run_cli(["--scan-json", "-", "--answers", ""], stdin="{nope\n")
        self.assertEqual((out["ok"], out["error"]), (False, "scan-rejected"))

    def test_bad_answers_is_usage(self):
        out = self.run_cli(["--no-scan", "--answers", "q1=maybe"])
        self.assertEqual((out["ok"], out["error"]), (False, "usage"))
        self.assertNotIn("maybe", json.dumps(out))  # never echoes answer text

    def test_internal_error_is_an_envelope(self):
        buf = io.StringIO()
        with mock.patch.object(cv, "decide", side_effect=RuntimeError("boom")), mock.patch("sys.stdout", buf):
            cv.main(["--no-scan", "--answers", ""])
        out = json.loads(buf.getvalue())
        self.assertEqual((out["ok"], out["error"]), (False, "internal"))


class VerdictMatchesProseRuleTests(unittest.TestCase):
    """The differential for a new judge: main has no script, so the floor is SKILL.md's door rule as written on
    main, applied by hand to realistic scans plus answers (fixtures/verdict/build_corpus.py, where each label says
    which prose step decides it). A more permissive door always fails. A stricter door fails unless listed here
    with the reason the prose was silent or wrong."""

    ALLOW_STRICTER = {
        # (corpus row id): (door the script may give, reason)
        "derived: deploy config and two environments | stop_line=none q1=yes q2=yes q3=yes q4=yes q5_data=yes q6=no q9=dont-know": (
            "patch-it", "the prose lets a founder fill only Don't know; a founder saying no to a scanner yes "
                        "(q6=no on a Vercel preview hint) is taken, which is the cautious reading of rule 5"),
    }
    PARTIAL_FOUNDER_YES = ("the prose's 'still Don't know' can be read as after the founder's answers; decided "
                           "10/15 that on a partial scan a founder yes cannot stand in for files the scanner never "
                           "read, so Q1/Q3 left open by the scan keep the door at Patch it with the rerun recipe")
    ALLOW_STRICTER.update(dict.fromkeys((
            "output over the cap with manifests the release did not read | stop_line=none q1=yes q2=yes q3=yes q4=yes q5_code=yes q5_data=yes q6=yes q9=yes",
            "opencode.jsonc counts toward max files | stop_line=none q1=yes q2=yes q3=yes q4=yes q5_code=yes q5_data=yes q6=yes q9=yes",
            "derived: oversize code file skipped | stop_line=none q1=yes q2=yes q3=yes q4=yes q5_code=yes q5_data=yes q6=yes q9=yes",
        ), ("patch-it", PARTIAL_FOUNDER_YES)))

    # The one door more permissive than main on purpose (the stop-line split, 0.3.5): checkout hosted by the payment
    # company is Gated work, not Get a person. (row id): (door the script may give, reason main was wrong).
    HOSTED = ("main ticked any \"payments\", so adding hosted Stripe subscriptions was Get a person; the split "
              "(decided 2026-09-30) keeps only card numbers in the app and money moved between people on the stop-line")
    ALLOW_PERMISSIVE = {
        "fb test mode | q1=dont-know q2=yes q3=dont-know q4=no q5_code=yes q5_data=no q6=yes q7=no q8=dont-know q9=no q10=yes q11=yes stop_line=none | hosted checkout": ("patch-it", HOSTED),
        "supabase init migration | q1=dont-know q2=yes q3=dont-know q4=no q5_code=yes q5_data=no q6=yes q7=no q8=dont-know q9=no q10=yes q11=yes stop_line=none | hosted checkout": ("patch-it", HOSTED),
        "rls disabled | q1=dont-know q2=yes q3=dont-know q4=no q5_code=yes q5_data=no q6=yes q7=no q8=dont-know q9=no q10=yes q11=yes stop_line=none | hosted checkout": ("patch-it", HOSTED),
        "degraded: scanner unavailable | q1=dont-know q2=yes q3=dont-know q4=no q5_code=yes q5_data=no q6=yes q7=no q8=dont-know q9=no q10=yes q11=yes stop_line=none | hosted checkout": ("patch-it", HOSTED),
    }

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FIXTURES, "verdict", "corpus.json"), encoding="utf-8") as fh:
            cls.corpus = json.load(fh)

    def test_only_hosted_checkout_may_be_more_permissive(self):
        for row_id, (door, reason) in self.ALLOW_PERMISSIVE.items():
            self.assertTrue(row_id.endswith("| hosted checkout"), row_id)
            self.assertIn("stop_line=none", row_id)
            self.assertIn(door, RANK)
            self.assertTrue(reason)

    def test_corpus_is_big_enough(self):
        self.assertGreaterEqual(len(self.corpus["rows"]), 40)
        self.assertGreaterEqual(len({r["scan"] for r in self.corpus["rows"]}), 15)

    def test_never_more_permissive_than_the_prose_rule(self):
        used, used_permissive = set(), set()
        for r in self.corpus["rows"]:
            scan = self.corpus["scans"][r["scan"]]
            v = cv.decide(copy.deepcopy(scan), cv.parse_answers(r["answers"]))
            got, want = v["door"], r["expected_door"]
            if RANK[got] > RANK[want]:
                self.assertEqual(self.ALLOW_PERMISSIVE.get(r["id"], (None,))[0], got,
                                 "%s: %s is more permissive than the prose rule's %s (%s)" % (r["id"], got, want, r["why"]))
                used_permissive.add(r["id"])
                continue
            if got != want:
                self.assertEqual(self.ALLOW_STRICTER.get(r["id"], (None,))[0], got,
                                 "%s: %s is stricter than the prose rule's %s and not listed" % (r["id"], got, want))
                used.add(r["id"])
            for q in r.get("expected_patch_head", []):
                self.assertIn(q, v["patch_list"], r["id"])
        self.assertEqual(set(self.ALLOW_STRICTER) - used, set(), "ALLOW_STRICTER entries no row needs")
        self.assertEqual(set(self.ALLOW_PERMISSIVE) - used_permissive, set(), "ALLOW_PERMISSIVE entries no row needs")

    def test_labels_quote_a_prose_step(self):
        steps = ("stop-line", "Q1, Q2 or Q3", "partial", "Two or more", "Otherwise", "git-index-unread")
        for r in self.corpus["rows"]:
            self.assertTrue(any(s in r["why"] for s in steps), r["id"])


if __name__ == "__main__":
    unittest.main()
