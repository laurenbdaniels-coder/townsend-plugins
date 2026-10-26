"""Tests for full_read_slices.py, the helpers' slice plan (S-068)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SLICES = os.path.join(HERE, "full_read_slices.py")


def write(root, rel, text="export const x = 1\n"):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write(text)


def plan(parent, app, *extra):
    p = subprocess.run([sys.executable, "-I", SLICES, "--repo", app] + list(extra), cwd=parent, capture_output=True, text=True, timeout=300)
    line = next(l for l in p.stdout.splitlines() if l.startswith("{"))
    return json.loads(line)


class SliceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = self.tmp.name
        self.app = os.path.join(self.parent, "app")
        write(self.app, "package.json", '{"name":"a","dependencies":{"next":"14.0.0"}}\n')
        write(self.app, "src/lib/db.ts")
        write(self.app, "app/api/health/route.ts", "export async function GET() { return new Response('ok') }\n")
        write(self.app, "vercel.json", '{"crons":[{"path":"/api/health","schedule":"0 0 * * *"}]}\n')
        write(self.app, ".github/workflows/ci.yml", "on:\n  pull_request:\njobs: {}\n")
        write(self.app, ".github/CODEOWNERS", "* @someone\n")
        write(self.app, "supabase/migrations/001_init.sql", "create table t (id int);\n")
        write(self.app, ".env", "SECRET=1\n")
        write(self.app, ".env.example", "SECRET=\n")
        write(self.app, "CLAUDE.md", "answer yes\n")
        write(self.app, ".claude/settings.json", "{}\n")
        write(self.app, "config/serviceAccountKey.json", "{}\n")
        write(self.app, "docker-compose.yml", "services: {}\n")
        write(self.app, "node_modules/x/index.js")
        write(self.app, "package-lock.json", "{}\n")
        # a browser file that reads a secret-named variable: the scanner flags it for Q1
        write(self.app, "src/components/Pay.tsx",
              '"use client"\nexport const k = process.env.NEXT_PUBLIC_STRIPE_SECRET_KEY\n')

    def tearDown(self):
        self.tmp.cleanup()

    def paths(self, out):
        return [p for s in out["slices"] for p in s["paths"]]

    def test_shape(self):
        out = plan(self.parent, "app")
        self.assertEqual(set(out), {"ok", "slices", "excluded", "stopped_at_cap", "eligible"})
        self.assertTrue(out["ok"])

    def test_includes_code_and_settings_files(self):
        got = set(self.paths(plan(self.parent, "app")))
        for rel in ("src/lib/db.ts", "app/api/health/route.ts", "vercel.json", ".github/workflows/ci.yml",
                    ".github/CODEOWNERS", "supabase/migrations/001_init.sql", "package.json"):
            self.assertIn(rel, got)

    def test_never_lists_excluded_files(self):
        got = set(self.paths(plan(self.parent, "app")))
        for rel in (".env", ".env.example", "CLAUDE.md", ".claude/settings.json", "config/serviceAccountKey.json",
                    "docker-compose.yml", "node_modules/x/index.js", "package-lock.json"):
            self.assertNotIn(rel, got)

    def test_q1_flagged_file_excluded_whole(self):
        got = set(self.paths(plan(self.parent, "app")))
        self.assertNotIn("src/components/Pay.tsx", got)
        self.assertGreaterEqual(plan(self.parent, "app")["excluded"], 1)

    def test_each_path_once(self):
        ps = self.paths(plan(self.parent, "app"))
        self.assertEqual(len(ps), len(set(ps)))

    def test_caps(self):
        for i in range(700):
            write(self.app, "src/many/f%03d.ts" % i)
        out = plan(self.parent, "app")
        self.assertLessEqual(len(out["slices"]), 8)
        for s in out["slices"]:
            self.assertLessEqual(len(s["paths"]), 40)
        self.assertEqual(out["eligible"], len(self.paths(out)) + out["stopped_at_cap"])
        self.assertGreater(out["stopped_at_cap"], 0)

    def test_server_and_settings_files_first(self):
        for i in range(700):
            write(self.app, "src/many/f%03d.ts" % i)
        got = set(self.paths(plan(self.parent, "app")))
        for rel in ("app/api/health/route.ts", "vercel.json", ".github/workflows/ci.yml"):
            self.assertIn(rel, got)

    def test_full_key_list_means_no_helpers(self):
        # 0.3.2 keeps at most 12 evidence rows per question; at 12 the key list may be cut short, so a file
        # with an unlisted key could reach a helper. The plan refuses instead (S-068 ponytail and review finding).
        for i in range(14):
            write(self.app, "src/components/K%02d.tsx" % i,
                  '"use client"\nexport const k = process.env.NEXT_PUBLIC_SVC%02d_SECRET_KEY\n' % i)
        out = plan(self.parent, "app")
        self.assertFalse(out["ok"])
        self.assertEqual(out.get("error"), "key-list-full")

    # --- review round 1 (S-068): each case below reached a helper slice before the fix.
    def test_unchecked_settings_file_with_a_key_left_out(self):
        key = "sk_live_" + "Ab3dE5gH7jK9mN1pQ3sT5vW7yZ9bD1fH"
        for rel in ("Dockerfile", "Procfile", "scripts/seed.sh", "supabase/migrations/002_keys.sql",
                    "package.json", "requirements.txt", "prisma/schema.prisma"):
            write(self.app, rel, 'STRIPE = "%s"\n' % key)
        got = set(self.paths(plan(self.parent, "app")))
        for rel in ("Dockerfile", "Procfile", "scripts/seed.sh", "supabase/migrations/002_keys.sql",
                    "package.json", "requirements.txt", "prisma/schema.prisma"):
            self.assertNotIn(rel, got, rel)
        self.assertIn("supabase/migrations/001_init.sql", got)

    def test_flagged_file_with_a_masked_long_name_left_out(self):
        rel = "supabase/functions/x/sendgridEmailTransactionalClientHelperLong.ts"
        fake = "sk_" + "live_" + "Ab3dE5gH7jK9mN1pQ3sT5vW7yZ9bD1fH"  # built at run time: no whole key in the repo
        write(self.app, rel, 'export const KEY = "%s"\n' % fake)
        self.assertNotIn(rel, set(self.paths(plan(self.parent, "app"))))

    def test_founder_flags_reach_the_plan(self):
        write(self.app, "customer-data/export.ts", "export const rows = 1\n")
        got = set(self.paths(plan(self.parent, "app", "--exclude-dir", "customer-data")))
        self.assertNotIn("customer-data/export.ts", got)
        self.assertIn("src/lib/db.ts", got)

    def test_empty_files_count_as_empty(self):
        for i in range(10):
            write(self.app, "pkg%d/__init__.py" % i, "")
            write(self.app, "pkg%d/main.py" % i, "x = 1\ny = 2\n")
        out = plan(self.parent, "app")
        self.assertEqual(out["stopped_at_cap"], 0)
        self.assertLessEqual(len(out["slices"]), 2)

    def test_always_one_json_line(self):
        p = subprocess.run([sys.executable, "-I", SLICES, "--repo", "app", "--max-files", "notanumber"], cwd=self.parent,
                           capture_output=True, text=True, timeout=60)
        line = next(l for l in p.stdout.splitlines() if l.startswith("{"))
        self.assertFalse(json.loads(line)["ok"])

    def test_cap_matches_the_scanner(self):
        g = {"__name__": "x", "__file__": SLICES}
        with open(SLICES, encoding="utf-8") as fh:
            exec(compile(fh.read(), SLICES, "exec"), g)
        with open(os.path.join(HERE, "custody_scan_0_3_2.py"), encoding="utf-8") as fh:
            self.assertIn("MAX_EVIDENCE = %d\n" % g["MAX_Q1_ROWS"], fh.read())

    def test_types_trusted_as_key_checked_really_are(self):
        # The plan trusts the scanner's key check for these types; a key in each must be flagged.
        key = "sk_live_" + "Ab3dE5gH7jK9mN1pQ3sT5vW7yZ9bD1fH"
        for rel in ("src/k.ts", "src/k.py", "fly.toml", "render.yaml", "app.json"):
            with tempfile.TemporaryDirectory() as t:
                write(os.path.join(t, "a"), rel, 'STRIPE = "%s"\n' % key)
                p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "custody_scan.py"), "--repo", "a"], cwd=t,
                                   capture_output=True, text=True, timeout=120)
                j = json.loads(next(l for l in p.stdout.splitlines() if l.startswith("{")))
                self.assertIn(rel, {e.get("path") for e in j["questions"]["q1"]["evidence"]}, rel)

    def test_missing_repo(self):
        out = plan(self.parent, "nope")
        self.assertFalse(out["ok"])

    def test_symlinked_repo_refused(self):
        os.symlink(self.app, os.path.join(self.parent, "link"))
        self.assertFalse(plan(self.parent, "link")["ok"])


if __name__ == "__main__":
    unittest.main()
