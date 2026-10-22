#!/bin/zsh
# Run build-decisions eval cases one at a time and add passing reports to the never-worse corpus.
#
# usage: build-decisions/evals/run-evals.sh <out-dir> <case[:runs]>...
#   e.g. build-decisions/evals/run-evals.sh ~/evals-0.6.0 seeded-app:3 fix-request stable-ranked:5
#   no-search:N runs evals-no-search/ alone with Grep and Glob taken away.
# env:  EVAL_COST_CEILING_USD (default 60) stops before the next case once the spend passes it.
#
# Needs: the sandbox off (claude plugin eval runs agents), python3 3.9+. Run from anywhere; it cds to the
# repo root's parent (~/Documents), which is where the evals have always run from.
# Resume: a case with <out-dir>/<case>.added (written once its reports joined the corpus) is skipped;
# a failed case runs again. A case's reports join
# free-plugin-standard/corpus/build-decisions-reports.jsonl only when every run of it passed.
set -euo pipefail

OUT=${1:?usage: run-evals.sh <out-dir> <case[:runs]>...}; shift
CEILING=${EVAL_COST_CEILING_USD:-60}
REPO=${0:A:h:h:h}
CORPUS=$REPO/free-plugin-standard/corpus/build-decisions-reports.jsonl
mkdir -p "$OUT"
cd "$REPO/.."

spent() {
  python3 - "$OUT" <<'PY'
import glob, json, sys
print(round(sum(json.load(open(f)).get("costUsd") or 0 for f in glob.glob(sys.argv[1] + "/*.json")), 2))
PY
}

for spec in "$@"; do
  name=${spec%%:*}; runs=1; [[ $spec == *:* ]] && runs=${spec##*:}
  json="$OUT/$name.json"; log="$OUT/$name.log"
  if [[ -e $OUT/$name.added ]]; then echo "skip $name (done)"; continue; fi
  rm -f "$json"
  total=$(spent)
  if (( $(python3 -c "print(1 if $total >= $CEILING else 0)") )); then
    echo "stop: spent \$$total, ceiling \$$CEILING; not starting $name" >&2; exit 3
  fi
  E=(--scaffold -j 1 --ablation none --runs "$runs" --json "$json")
  if [[ $name == no-search ]]; then
    E+=(--disallow-tools Grep Glob); target=(./"${REPO:t}"/build-decisions --eval-dir evals-no-search)
  else
    E+=(--case "$name"); target=(./"${REPO:t}"/build-decisions)
  fi
  echo "run $name x$runs (spent so far \$$total)"
  if ! claude plugin eval "${target[@]}" "${E[@]}" >"$log" 2>&1; then
    echo "FAIL $name: claude plugin eval exited non-zero; log $log" >&2
  fi
  # Add the reports only when the case's every run passed (the report text comes from each run's trace).
  if python3 - "$json" "$CORPUS" "$name" <<'PY'; then touch "$OUT/$name.added"; else echo "FAIL $name: not added to the corpus; log ${log}" >&2; fi
import json, sys
path, corpus, name = sys.argv[1:]
d = json.load(open(path))
rows = []
for case in d["cases"]:
    runs = case["arms"]["with"]
    if not runs or not all(r.get("passed") for r in runs):
        sys.exit("%s: %d of %d runs passed" % (case["name"], sum(bool(r.get("passed")) for r in runs), len(runs)))
    for r in runs:
        text = None
        for line in open(r["tracePath"]):
            ev = json.loads(line)
            if ev.get("type") == "result" and ev.get("result"):
                text = ev["result"]
        if not text:
            sys.exit("%s: no report text in %s" % (case["name"], r["tracePath"]))
        version = text.rsplit("build-decisions v", 1)[-1].split(" ", 1)[0] if "build-decisions v" in text else None
        rows.append({"case": case["name"], "text": text, "version": version})
with open(corpus, "a") as fh:
    for row in rows:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
print("added %d reports from %s" % (len(rows), name))
PY
done
echo "done: spent \$$(spent)"
