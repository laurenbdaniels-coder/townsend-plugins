"""Builds corpus.json for VerdictMatchesProseRuleTests (custody_verdict_test.py).

Scans: released main's scanner (exported with git archive, as in ../differential/build_cases.py) run on the seeded
app and on cases from the differential corpus, plus a few shapes the files cannot produce cheaply, each derived from
a real scan and named "derived: ...". Snippets are blanked except on Q10 (field names, which the stop-line reads) and
the git-index-unread row, so no key-shaped text is stored.

Doors: LABELS, written by hand from SKILL.md's `## Door rule` as it is on main, one per (scan, answers) row, each
with the prose step that decides it. Never computed by custody_verdict.py: that is what the test checks.

From the repo root:
    python3 custody-check/skills/custody-check/scripts/fixtures/verdict/build_corpus.py origin/main --summary
    python3 custody-check/skills/custody-check/scripts/fixtures/verdict/build_corpus.py origin/main \
        custody-check/skills/custody-check/scripts/fixtures/verdict/corpus.json
"""
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("custody_build_cases", os.path.join(FIXTURES, "differential", "build_cases.py"))
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)

CASES = [
    "client key", "cts client key", "server only key in components", "rls disabled", "fb if true", "rtdb open",
    "fb test mode", "fb owner only", "table without rls", "seed only", "public view", "supabase init migration",
    "vite server-only import", "monitoring family in requirements", "pii after a string glob and a comment close",
    "comma inside a quoted dropped name", "pii field just under the cap",
    "output over the cap with manifests the release did not read", "firestore test mode just over the cap",
    "opencode.jsonc counts toward max files",
]

# Answer sets (custody_verdict --answers tokens). The founder answers only what they are asked; these are the shapes.
NONE = ""
ALL_YES = "stop_line=none q1=yes q2=yes q3=yes q4=yes q5_code=yes q5_data=yes q6=yes q9=yes"
ONE_OF_FOUR = "stop_line=none q1=yes q2=yes q3=yes q4=yes q5_code=yes q5_data=yes q6=yes q9=dont-know"
TWO_OF_FOUR = "stop_line=none q1=yes q2=yes q3=yes q4=dont-know q5_code=yes q5_data=yes q6=yes q9=no"
EXAMPLE = ("q1=dont-know q2=yes q3=dont-know q4=no q5_code=yes q5_data=no q6=yes q7=no q8=dont-know q9=no q10=yes "
           "q11=yes stop_line=payments")  # the 0.3.4 answers example (stop_line: payments), an old block that still ticks
HEALTH = "stop_line=health q1=yes q2=yes q3=yes q4=yes q5_code=yes q5_data=yes q6=yes q9=yes"

# The stop-line split (0.3.5). Each row's answers are the tokens the skill sends under the new mapping; the label is
# the door main's written rule gives for the same founder words. Main ticked any "payments", so the hosted-checkout
# founder (the example block: "add Stripe subscriptions") was Get a person there. That row is the one door listed as
# more permissive on purpose (custody_verdict_test ALLOW_PERMISSIVE).
HOSTED_CHECKOUT = EXAMPLE.replace("stop_line=payments", "stop_line=none")
CARD_NUMBERS = ALL_YES.replace("stop_line=none", "stop_line=card-numbers")
MOVES_MONEY = ALL_YES.replace("stop_line=none", "stop_line=moves-money")
LEGACY_PAYMENTS = ALL_YES.replace("stop_line=none", "stop_line=payments")  # an old block; the founder was not asked
# Widened 2026-10-15 (review round 2): invoices and refunds the payment company runs are processor-handled too. The
# founder said a clear no to card details and to money held for others, so the skill sends stop_line=none.
PROCESSOR_INVOICES = ALL_YES

SKIPPED_Q1_Q3 = "stop_line=none q2=yes q4=yes q5_code=yes q5_data=yes q6=yes q9=yes"  # founder left Q1/Q3 alone
FOUNDER_NO_ON_YES = "stop_line=none q1=yes q2=yes q3=yes q4=yes q5_data=yes q6=no q9=dont-know"

# (scan, answers, expected door per the prose rule, why). Read the scan summary (--summary) before labelling.
LABELS = []


def label(scan, answers, door, why, tag=None):
    row_id = "%s | %s" % (scan, answers or "no answers") + (" | %s" % tag if tag else "")
    LABELS.append({"id": row_id, "scan": scan, "answers": answers,
                   "expected_door": door, "why": why})


# Scanner No on Q1 or Q3, complete scan, no stop-line field on Q10.
for s in ("client key", "cts client key", "server only key in components", "vite server-only import",
          "rls disabled", "fb if true", "rtdb open"):
    label(s, NONE, "patch-it", "Q1, Q2 or Q3 is no (scanner No; nothing ticks the stop-line)")
    label(s, ALL_YES, "patch-it", "Q1, Q2 or Q3 is no: a founder answer never changes a scanner no")
    label(s, ONE_OF_FOUR, "patch-it", "Q1, Q2 or Q3 is no")
    label(s, EXAMPLE, "get-a-person", "stop-line ticked by the founder (payments) comes first")

# No scanner No, complete scan, no stop-line field: the door turns on the founder's answers.
for s in ("fb test mode", "fb owner only", "table without rls", "seed only", "public view",
          "supabase init migration", "monitoring family in requirements"):
    label(s, NONE, "patch-it", "Two or more of Q4, Q5, Q6, Q9 are Don't know (none answered; Q5 data is Don't know)")
    label(s, ALL_YES, "ship-it", "Otherwise: the founder filled every Don't know / Nothing found with yes, scan complete")
    label(s, ONE_OF_FOUR, "ship-it", "Otherwise: only Q9 is Don't know, one of Q4, Q5, Q6, Q9 is not two")
    label(s, TWO_OF_FOUR, "patch-it", "Two or more of Q4, Q5, Q6, Q9 are no or Don't know (Q4 Don't know, Q9 no)")
    label(s, HEALTH, "get-a-person", "stop-line ticked by the founder (health)")

# Q10 evidence shows a stop-line field: Get a person whatever the founder says.
for s in ("seeded-app", "pii after a string glob and a comment close", "comma inside a quoted dropped name",
          "pii field just under the cap", "firestore test mode just over the cap", "derived: camelCase birth date field"):
    label(s, NONE, "get-a-person", "stop-line: Q10 evidence shows a field from rule 6's list")
    label(s, ALL_YES, "get-a-person", "stop-line: Q10 evidence shows a field from rule 6's list, stop_line none notwithstanding")

# The stop-line split. Card numbers, money between people and an unanswered old "payments" tick, as on main.
for s in ("fb test mode", "supabase init migration", "rls disabled", "seeded-app", "degraded: scanner unavailable"):
    label(s, CARD_NUMBERS, "get-a-person", "stop-line ticked by the founder (card numbers in the app)")
    label(s, MOVES_MONEY, "get-a-person", "stop-line ticked by the founder (money moved between people)")
    label(s, LEGACY_PAYMENTS, "get-a-person", "stop-line ticked by the founder (payments, the old word, not followed up)")
    label(s, HOSTED_CHECKOUT, "get-a-person",
          "stop-line ticked by the founder on main: the founder said payments (hosted checkout: add Stripe subscriptions)",
          tag="hosted checkout")
    label(s, PROCESSOR_INVOICES, "get-a-person",
          "stop-line ticked by the founder on main: the founder said payments (invoices and refunds the payment company runs)",
          tag="processor invoices")

# Partial scans, Q1 and Q3 Don't know, no stop-line field.
for s in ("output over the cap with manifests the release did not read", "opencode.jsonc counts toward max files",
          "derived: oversize code file skipped"):
    label(s, NONE, "patch-it", "partial with Q1 or Q3 still Don't know: never Ship it, rerun recipe")
    label(s, SKIPPED_Q1_Q3, "patch-it", "partial with Q1 or Q3 still Don't know: the founder did not answer them")
    label(s, ALL_YES, "ship-it", "Otherwise: partial, but the founder answered Q1 and Q3, so neither is still Don't know")
    label(s, TWO_OF_FOUR, "patch-it", "Two or more of Q4, Q5, Q6, Q9 (partial step cleared by the founder's Q1/Q3)")

# git's index unread on Q1.
for a in (NONE, ALL_YES, ONE_OF_FOUR):
    label("derived: git index unread", a, "patch-it", "git-index-unread on Q1: Don't know (git not read), the door is never Ship it")

# Degraded path: no scanner, so no partial flag; Q1/Q3 Don't know do not decide on their own (a weakness main has).
label("degraded: scanner unavailable", NONE, "patch-it", "Two or more of Q4, Q5, Q6, Q9 are Don't know (scanner unavailable)")
label("degraded: scanner unavailable", ALL_YES, "ship-it", "Otherwise: the founder answered every question yes")
label("degraded: scanner unavailable", SKIPPED_Q1_Q3, "ship-it",
      "Otherwise: not partial, so Q1/Q3 Don't know do not block; Q4, Q5, Q6, Q9 are yes")
label("degraded: scanner unavailable", EXAMPLE, "get-a-person", "stop-line ticked by the founder (payments)")

# Scanner yes on Q5 code and Q6.
label("derived: deploy config and two environments", ALL_YES, "ship-it", "Otherwise: scanner yes on Q5 code and Q6, founder yes elsewhere")
label("derived: deploy config and two environments", FOUNDER_NO_ON_YES, "ship-it",
      "Otherwise: the founder's q6=no does not fill a scanner yes (answers fill only Don't know), so only Q9 fails")


def _blank(scan):
    for q, part in scan["questions"].items():
        for p in ([part["code"], part["data"]] if q == "q5" else [part]):
            for e in p["evidence"]:
                if q != "q10" and e["check"] != "git-index-unread":
                    e["snippet"] = ""
    return scan


def run(scanner, cwd, app, args=()):
    out = subprocess.run([sys.executable, "-I", scanner, "--repo", app] + list(args), cwd=cwd, capture_output=True,
                         text=True, timeout=600).stdout
    return _blank(json.loads(out))


def build_scans(scanner):
    scans = {"seeded-app": run(scanner, FIXTURES, "seeded-app")}
    for name in CASES:
        c = next(x for x in bc.cases if x["name"] == name)
        tmp = tempfile.mkdtemp()
        try:
            bc.materialize(os.path.join(tmp, "app"), c)
            flags = []
            for k, v in sorted(c.get("args", {}).items()):
                flags += ["--" + k.replace("_", "-"), str(v)]
            scans[name] = run(scanner, tmp, "app", flags)
        finally:
            shutil.rmtree(tmp)
    # derived: a scan where git's index could not be read (Q1 evidence row; the scan is partial)
    d = copy.deepcopy(scans["supabase init migration"])
    d["partial"] = True
    d["stats"]["git_index_partial"] = 1
    d["questions"]["q1"] = {"answer": "dont-know", "confidence": "low", "evidence": [
        {"path": "", "line": 0, "snippet": "git's file index was not read, so committed secrets could not be checked",
         "check": "git-index-unread"}]}
    scans["derived: git index unread"] = d
    # derived: partial because a large code file was skipped; Q1 Don't know, Q3 a No elsewhere is absent
    d = copy.deepcopy(scans["supabase init migration"])
    d["partial"] = True
    d["stats"]["files_skipped_oversize_relevant"] = 1
    d["questions"]["q1"]["answer"] = "dont-know"
    d["questions"]["q1"]["evidence"] = [{"path": "", "line": 0, "snippet": "", "check": "scan-summary"}]
    scans["derived: oversize code file skipped"] = d
    # derived: camelCase stop-line field on Q10 of an otherwise ordinary app
    d = copy.deepcopy(scans["supabase init migration"])
    d["questions"]["q10"] = {"answer": "dont-know", "confidence": "low", "evidence": [
        {"path": "src/types.ts", "line": 3, "snippet": "dateOfBirth", "check": "pii-field"}]}
    scans["derived: camelCase birth date field"] = d
    # derived: the scanner's two yes-parts (a deploy config for Q5 code, two named environments for Q6)
    d = copy.deepcopy(scans["supabase init migration"])
    d["questions"]["q5"]["code"] = {"answer": "yes", "confidence": "med", "evidence": [
        {"path": "vercel.json", "line": 0, "snippet": "", "check": "deploy-config"}]}
    d["questions"]["q6"] = {"answer": "yes", "confidence": "med", "evidence": [
        {"path": ".env.staging", "line": 0, "snippet": "", "check": "env-name"}]}
    scans["derived: deploy config and two environments"] = d
    scans["degraded: scanner unavailable"] = None
    return scans


def summary(scans):
    for name, s in scans.items():
        if s is None:
            print("%-62s DEGRADED" % name)
            continue
        q = s["questions"]
        ans = " ".join("%s=%s" % (k, (q[k]["code"]["answer"] if k == "q5" else q[k]["answer"])) for k in sorted(q, key=lambda x: int(x[1:])))
        q10 = sorted({e["snippet"] for e in q["q10"]["evidence"]})
        q1c = sorted({e["check"] for e in q["q1"]["evidence"]})
        print("%-62s partial=%s %s\n%62s q10=%s q1checks=%s oversize_rel=%s" % (
            name, s["partial"], ans, "", q10, q1c, s["stats"].get("files_skipped_oversize_relevant")))


if __name__ == "__main__":
    ref, dest = sys.argv[1], sys.argv[2]
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE, capture_output=True, text=True,
                          check=True).stdout.strip()
    tmp = tempfile.mkdtemp()
    try:
        scanner, sha = bc.export_release(ref, tmp, root)
        version = subprocess.run([sys.executable, "-I", scanner, "--version"], capture_output=True, text=True).stdout.strip()
        scans = build_scans(scanner)
    finally:
        shutil.rmtree(tmp)
    if dest == "--summary":
        summary(scans)
        sys.exit(0)
    missing = {r["scan"] for r in LABELS} - set(scans)
    if missing:
        sys.exit("labels name scans that were not built: %s" % sorted(missing))
    with open(dest, "w") as fh:
        json.dump({"baseline": "SKILL.md door rule on main %s; scans from custody-check %s" % (sha[:7], version),
                   "baseline_sha": sha, "scans": scans, "rows": LABELS}, fh, indent=1, sort_keys=True)
    print(len(LABELS), "rows,", len(scans), "scans written")
