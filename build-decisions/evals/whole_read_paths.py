"""The files each eval case may read whole (limit 401): the case app's value_handlers, as the helper lists them.

Run from the repo root: python3 build-decisions/evals/whole_read_paths.py [--write]
--write restamps each case's read-at-most-120-lines grader so a 401-line read is allowed only on those files;
without it, it prints the paths and exits 1 when any case is stale (report_graders_test runs the same check).
"""
import json
import os
import re
import subprocess
import sys
import tempfile

EVALS = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(EVALS)
HELPER = os.path.join(PLUGIN, "skills", "build-decisions", "scripts", "census_scan.py")
OVER_120 = r'"limit"\s*:\s*(?:12[1-9]|1[3-9]\d|[2-9]\d\d|\d{4,})'


def case_dirs():
    for root in ("evals", "evals-no-search"):
        base = os.path.join(PLUGIN, root)
        for name in sorted(os.listdir(base)):
            if os.path.isfile(os.path.join(base, name, "case.yaml")):
                yield os.path.join(base, name)


def app_of(case_yaml):
    m = re.search(r'prompt: "[^"]*\./([A-Za-z0-9_-]+)', case_yaml)
    return m.group(1) if m else None


def paths_for(case_dir):
    text = open(os.path.join(case_dir, "case.yaml"), encoding="utf-8").read()
    app = app_of(text)
    if not app or not os.path.exists(os.path.join(case_dir, "scaffold.sh")):
        return app, []
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["bash", os.path.join(case_dir, "scaffold.sh")], cwd=tmp, check=True, capture_output=True)
        out = subprocess.run([sys.executable, "-I", HELPER, "--repo", app, "--section", "architecture"],
                             cwd=tmp, capture_output=True, text=True).stdout
    return app, json.loads(out).get("value_handlers", [])


def pattern(app, paths):
    if not paths:
        return OVER_120
    alts = "|".join(re.escape(p) for p in paths)
    return (r'^(?![\s\S]*"file_path"\s*:\s*"[^"]*/%s/(?:%s)"[\s\S]*"limit"\s*:\s*401\b)[\s\S]*%s'
            % (re.escape(app), alts, OVER_120))


GRADER = re.compile(r'(  - name: "read-at-most-120-lines"\n    type: "tool_used"\n    tool: "Read"\n    input_match: )(.*)\n')


def main(write):
    stale = []
    for d in case_dirs():
        app, paths = paths_for(d)
        f = os.path.join(d, "case.yaml")
        text = open(f, encoding="utf-8").read()
        m = GRADER.search(text)
        if not m:
            continue
        want = json.dumps(pattern(app, paths))
        if m.group(2) != want:
            stale.append(os.path.basename(d))
            if write:
                text = text[:m.start(2)] + want + text[m.end(2):]
                open(f, "w", encoding="utf-8").write(text)
        print(os.path.basename(d), app, paths)
    if stale and not write:
        print("stale:", " ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv))
