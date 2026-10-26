"""Tests for census_scan.py --section warnings (python 3.9, unittest only).

0.7.0 ships one kind of warning, several-ways: one job done with two or more libraries, each declared by the app
and used in at least one of its source files (S-059 K1; the other two kinds were cut by their samples). Every test
docstring carries its card: protects / fails_when / no_claim. Trees are built at test time in a temporary folder.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import census_scan as cs  # noqa: E402
from census_scan_test import run, write  # noqa: E402

WARN_KEYS = {"ok", "section", "partial", "version", "coverage", "partial_reasons", "stats", "findings", "totals"}
FINDING_KEYS = {"kind", "app", "job", "count", "places", "more"}
PLACE_KEYS = {"path", "line", "name"}
TOTAL_KEYS = {"findings", "listed", "not_listed"}


def pkg(deps=None, dev=None):
    obj = {"name": "web", "dependencies": dict.fromkeys(deps or (), "1.0.0")}
    if dev:
        obj["devDependencies"] = dict.fromkeys(dev, "1.0.0")
    return json.dumps(obj, indent=2)


class WarnCase(unittest.TestCase):
    def setUp(self):
        self.parent = tempfile.mkdtemp(prefix="warn-test-")
        self.repo = os.path.join(self.parent, "app")
        os.makedirs(self.repo)

    def tearDown(self):
        shutil.rmtree(self.parent, ignore_errors=True)

    def w(self, rel, text):
        return write(self.repo, rel, text)

    def warn(self, *extra):
        result, line, _ = run(self.parent, "app", "--section", "warnings", *extra)
        self.line = line
        return result

    def jobs(self, result):
        return sorted((f["app"], f["job"]) for f in result["findings"])

    def places(self, finding):
        return [(p["name"], p["path"], p["line"]) for p in finding["places"]]


# ------------------------------------------------------------------- contract

class ContractTests(WarnCase):
    def test_keys_and_one_line(self):
        """protects=the skill's accept check (exact keys, closed ids);
        fails_when=a key is added, dropped or renamed, or a finding carries anything but the closed fields;
        no_claim=the founder wording (SKILL.md)."""
        self.w("package.json", pkg(["axios", "ky"]))
        self.w("src/a.ts", "import axios from 'axios'\n")
        self.w("src/b.ts", "import ky from 'ky'\n")
        r = self.warn()
        self.assertEqual(set(r), WARN_KEYS)
        self.assertTrue(r["ok"])
        self.assertEqual(r["section"], "warnings")
        self.assertEqual(r["version"], cs.__version__)
        self.assertEqual(set(r["totals"]), TOTAL_KEYS)
        self.assertEqual(len(r["findings"]), 1)
        f = r["findings"][0]
        self.assertEqual(set(f), FINDING_KEYS)
        self.assertEqual(f["kind"], "several-ways")
        self.assertIn(f["job"], cs.WARN_JOBS)
        for p in f["places"]:
            self.assertEqual(set(p), PLACE_KEYS)
        self.assertLessEqual(len(self.line.encode("utf-8")), cs.MAX_OUTPUT_BYTES)

    def test_every_string_is_a_path_or_fixed_vocabulary(self):
        """protects=nothing from inside a file reaches the output;
        fails_when=a string value is neither a real repo-relative path nor in cs.WARN_VOCABULARY;
        no_claim=numbers."""
        self.w("package.json", pkg(["axios", "ky", "zustand", "jotai"]))
        self.w("src/a.ts", "import axios from 'axios'\nimport { create } from 'zustand'\n")
        self.w("src/b.ts", "import ky from 'ky'\nimport { atom } from 'jotai'\n")
        r = self.warn()
        self.assertEqual(len(r["findings"]), 2)

        def strings(obj, key=None):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    yield from strings(v, k)
            elif isinstance(obj, list):
                for v in obj:
                    yield from strings(v, key)
            elif isinstance(obj, str):
                yield key, obj
        for key, s in strings(r):
            if key in ("path", "app"):
                self.assertTrue(os.path.exists(os.path.join(self.repo, *s.split("/"))), s)
            elif key != "version":
                self.assertIn(s, cs.WARN_VOCABULARY, "%s=%r is not fixed vocabulary" % (key, s))

    def test_job_ids_are_the_closed_table(self):
        """protects=Y1/C8: only the sampled families ship (HTTP, state, dates, forms), and Tailwind is in none;
        fails_when=a family or a library is added without a sample, or tailwindcss joins a family;
        no_claim=whether the families are complete."""
        self.assertEqual(cs.WARN_JOBS, ("http", "state", "dates", "forms"))
        self.assertEqual(set(cs.JOB_FAMILIES), set(cs.WARN_JOBS))
        self.assertEqual(cs.JOB_FAMILIES["http"], ("axios", "ky", "got", "node-fetch", "superagent", "requests",
                                                   "httpx", "aiohttp"))
        self.assertEqual(cs.JOB_FAMILIES["state"], ("redux", "@reduxjs/toolkit", "zustand", "jotai", "recoil",
                                                    "mobx", "valtio"))
        self.assertEqual(cs.JOB_FAMILIES["dates"], ("moment", "dayjs", "date-fns", "luxon"))
        self.assertEqual(cs.JOB_FAMILIES["forms"], ("react-hook-form", "formik"))
        self.assertFalse(any("tailwind" in lib for libs in cs.JOB_FAMILIES.values() for lib in libs))

    def test_no_warnings_is_an_empty_list(self):
        """protects=zero warnings prints nothing in the report (§3.1): the helper says so with an empty list;
        fails_when=an app with one HTTP library gets a finding;
        no_claim=the report text."""
        self.w("package.json", pkg(["axios"]))
        self.w("src/a.ts", "import axios from 'axios'\n")
        r = self.warn()
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["totals"], {"findings": 0, "listed": 0, "not_listed": 0})

    def test_internal_error_has_its_own_code(self):
        """protects=X3/E16: a crash in the warnings run says so with its own code and hint, and never a traceback;
        fails_when=the census hint or a traceback is printed;
        no_claim=the other sections (they run in their own processes)."""
        self.w("package.json", pkg(["axios", "ky"]))
        with mock.patch.object(cs, "warn_findings", side_effect=RuntimeError("boom")), \
                mock.patch.object(sys, "stdout") as out:
            cwd = os.getcwd()
            os.chdir(self.parent)
            try:
                cs.main(["--repo", "app", "--section", "warnings"])
            finally:
                os.chdir(cwd)
        text = "".join(c.args[0] for c in out.write.call_args_list)
        obj = json.loads(text)
        self.assertEqual(obj["error"], "internal-warnings")
        self.assertEqual(obj["hint"], cs.HINTS["internal-warnings"])
        self.assertNotIn("boom", text)


# ------------------------------------------------------------------- what counts as a use

class UseTests(WarnCase):
    def test_two_libraries_each_used_once(self):
        """protects=the round-2 rule (Lauren 10/25): each library used in at least 1 source file;
        fails_when=two used HTTP libraries give no finding;
        no_claim=which of the two the app should keep (never said)."""
        self.w("package.json", pkg(["axios", "ky"]))
        self.w("src/api/a.ts", "// client\nimport axios from 'axios'\n")
        self.w("src/api/b.ts", "import ky from 'ky'\n")
        r = self.warn()
        self.assertEqual(self.jobs(r), [(".", "http")])
        f = r["findings"][0]
        self.assertEqual(f["count"], 2)
        self.assertEqual(f["more"], 0)

    def test_declared_only_does_not_count(self):
        """protects=declared-only libraries are K3's ground, not K1's (§2.2);
        fails_when=a declared library no file uses makes a finding;
        no_claim=unused packages (not in 0.7.0)."""
        self.w("package.json", pkg(["axios", "ky"]))
        self.w("src/a.ts", "import axios from 'axios'\n")
        r = self.warn()
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["coverage"], [{"app": ".", "k1": "checked"}])

    def test_used_but_not_declared_does_not_count(self):
        """protects=a library must be declared by the app (the floor reads the manifest);
        fails_when=an import of an undeclared library counts;
        no_claim=libraries a workspace parent declares."""
        self.w("package.json", pkg(["axios", "ky"]))
        self.w("src/a.ts", "import axios from 'axios'\n")
        self.w("src/b.ts", "import got from 'got'\n")
        self.assertEqual(self.warn()["findings"], [])

    def test_dev_dependencies_count_as_declared(self):
        """protects=the frozen prototype: devDependencies are declared for K1 (a used library is a use wherever
        the manifest lists it);
        fails_when=a library listed under devDependencies and used in source is ignored;
        no_claim=K3, which never lists devDependencies."""
        self.w("package.json", pkg(["axios"], dev=["ky"]))
        self.w("src/a.ts", "import axios from 'axios'\n")
        self.w("src/b.ts", "import ky from 'ky'\n")
        self.assertEqual(self.jobs(self.warn()), [(".", "http")])

    def test_import_forms(self):
        """protects=require, dynamic import, export-from and subpaths are uses;
        fails_when=any of these forms is missed;
        no_claim=imports built from variables (never resolvable)."""
        self.w("package.json", pkg(["moment", "dayjs", "date-fns", "luxon"]))
        self.w("src/a.js", "const moment = require('moment')\n")
        self.w("src/b.ts", "const d = await import('dayjs')\n")
        self.w("src/c.ts", "export { format } from 'date-fns/format'\n")
        self.w("src/d.vue", "<script>\nimport { DateTime } from 'luxon'\n</script>\n")
        f = self.warn()["findings"][0]
        self.assertEqual(f["job"], "dates")
        self.assertEqual(f["count"], 4)

    def test_tests_stories_fixtures_examples_do_not_count(self):
        """protects=only the app's own source counts (round 2);
        fails_when=a library used only in a test, story, fixture or example makes a finding;
        no_claim=whether those files are themselves needed."""
        self.w("package.json", pkg(["axios", "ky", "got", "node-fetch", "superagent"]))
        self.w("src/a.ts", "import axios from 'axios'\n")
        self.w("src/b.test.ts", "import ky from 'ky'\n")
        self.w("src/c.stories.tsx", "import got from 'got'\n")
        self.w("fixtures/d.ts", "import fetch from 'node-fetch'\n")
        self.w("examples/e.ts", "import superagent from 'superagent'\n")
        self.w("__tests__/f.ts", "import ky from 'ky'\n")
        self.assertEqual(self.warn()["findings"], [])

    def test_commented_out_import_does_not_count(self):
        """protects=round 2: a commented-out import is not a use;
        fails_when=`// import ky from 'ky'` counts;
        no_claim=imports inside multi-line strings."""
        self.w("package.json", pkg(["axios", "ky"]))
        self.w("src/a.ts", "import axios from 'axios'\n// import ky from 'ky'\n/* import ky from 'ky' */\n")
        self.assertEqual(self.warn()["findings"], [])

    def test_mdx_is_not_a_place(self):
        """protects=the sample-gate build fix (guarahooks): a docs page is never a K1 place or use;
        fails_when=a library used only in an .mdx file makes a finding;
        no_claim=whether docs pages show real usage."""
        self.w("package.json", pkg(["axios", "ky"]))
        self.w("src/a.ts", "import axios from 'axios'\n")
        self.w("content/docs/ky.mdx", "import ky from 'ky'\n\n# Using ky\n")
        self.assertEqual(self.warn()["findings"], [])

    def test_redux_toolkit_and_redux_are_one_library(self):
        """protects=§2.2 lists redux/@reduxjs/toolkit as one library: Redux Toolkit is redux (review round 1, 10/26);
        fails_when=an app that declares both and imports a redux type gets a state warning;
        no_claim=redux beside a different state library (still a warning, test below)."""
        self.w("package.json", pkg(["@reduxjs/toolkit", "redux", "react-redux"]))
        self.w("src/store/index.ts", "import { configureStore } from '@reduxjs/toolkit'\n")
        self.w("src/store/logger.ts", "import type { Middleware } from 'redux'\n")
        r = self.warn()
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["coverage"], [{"app": ".", "k1": "below_floor"}])
        self.w("package.json", pkg(["@reduxjs/toolkit", "redux", "zustand"]))
        self.w("src/ui.ts", "import { create } from 'zustand'\n")
        f = self.warn()["findings"]
        self.assertEqual([(x["job"], [p["name"] for p in x["places"]]) for x in f],
                         [("state", ["@reduxjs/toolkit", "zustand"])])

    def test_a_website_and_a_python_server_are_not_one_job(self):
        """protects=one finding never pairs a JavaScript library with a Python one: they can never be merged
        (Next.js + Flask template; review round 1, 10/26);
        fails_when=axios on the site and requests on the server in one folder make a warning;
        no_claim=two libraries in one language (still a warning)."""
        self.w("package.json", pkg(["axios", "next"]))
        self.w("requirements.txt", "flask\nrequests\n")
        self.w("app/page.tsx", "import axios from 'axios'\n")
        self.w("api/index.py", "from flask import Flask\nimport requests\n")
        r = self.warn()
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["coverage"], [{"app": ".", "k1": "below_floor"}])
        self.w("requirements.txt", "flask\nrequests\nhttpx\n")
        self.w("api/other.py", "import httpx\n")
        self.assertEqual([[p["name"] for p in x["places"]] for x in self.warn()["findings"]], [["requests", "httpx"]])

    def test_aiohttp_as_a_web_server_is_not_a_request_library(self):
        """protects=aiohttp counts only where the app sends requests with it, not where it serves them
        (bot/webhook shape; review round 1, 10/26);
        fails_when=`from aiohttp import web` beside requests makes an HTTP warning;
        no_claim=`import aiohttp` (still counts: it may be the client)."""
        self.w("requirements.txt", "aiohttp==3.9.5\nrequests==2.32.3\n")
        self.w("app/server.py", "from aiohttp import web\nimport requests\n\nasync def hook(req):\n"
                                "    requests.post('https://example.com')\n")
        self.w("app/routes.py", "import aiohttp.web\nfrom aiohttp.web import Application\n")
        self.assertEqual(self.warn()["findings"], [])
        self.w("app/client.py", "from aiohttp import ClientSession, web\n")
        self.assertEqual([[p["name"] for p in x["places"]] for x in self.warn()["findings"]],
                         [["aiohttp", "requests"]])

    def test_triple_quoted_strings_never_hide_real_imports(self):
        """protects=round-2 review (10/26): a real import after a triple-quoted string still counts; a per-line
        comment rule only (block comments and docstrings are a known gap, TODOS);
        fails_when=an r-docstring or a cur.execute(\"\"\"...\"\"\") before a later import hides the import;
        no_claim=imports inside the strings themselves (they count today: known false alarm)."""
        self.w("requirements.txt", "requests\nhttpx\n")
        self.w("a/fetch.py", 'r"""Fetch helpers.\n\nMore text.\n"""\nimport requests\n')
        self.w("a/db.py", 'def rows(cur):\n    cur.execute("""\n        SELECT 1\n    """)\n\n\n'
                          'def later():\n    import httpx\n    return httpx\n')
        self.assertEqual([x["job"] for x in self.warn()["findings"]], ["http"])

    def test_python_requests_and_httpx(self):
        """protects=stratum (c): a Python app with requests and httpx;
        fails_when=Python imports or requirements.txt are not read;
        no_claim=Python test files (skipped, below)."""
        self.w("requirements.txt", "requests==2.31.0\nhttpx[http2]>=0.27 ; python_version > '3.8'\n")
        self.w("app/client.py", "import os\nimport requests\n")
        self.w("app/fast.py", "from httpx import AsyncClient\n")
        self.w("app/test_client.py", "import aiohttp\n")
        r = self.warn()
        self.assertEqual(self.jobs(r), [(".", "http")])
        self.assertEqual(self.places(r["findings"][0]),
                         [("requests", "app/client.py", 2), ("httpx", "app/fast.py", 1)])

    def test_pyproject_both_shapes(self):
        """protects=C9/C50: [project].dependencies and [tool.poetry.dependencies] are both read;
        fails_when=either table is missed;
        no_claim=other Python manifests (none list anything)."""
        self.w("svc-a/pyproject.toml", '[project]\nname = "a"\ndependencies = [\n  "requests>=2",\n  "httpx",\n]\n')
        self.w("svc-a/main.py", "import requests\nimport httpx\n")
        self.w("svc-b/pyproject.toml", '[tool.poetry.dependencies]\npython = "^3.11"\naiohttp = "^3.9"\n'
                                       'requests = "^2.31"\n')
        self.w("svc-b/main.py", "import aiohttp\nimport requests\n")
        self.assertEqual(self.jobs(self.warn()), [("svc-a", "http"), ("svc-b", "http")])

    def test_unreadable_pyproject_declares_nothing(self):
        """protects=the frozen prototype: a pyproject.toml this reader cannot handle means the folder declares no
        Python library, even with a requirements.txt beside it (no finding from half a manifest);
        fails_when=requirements.txt names still count next to an unhandled pyproject.toml;
        no_claim=which pyproject shapes are common."""
        self.w("requirements.txt", "requests\nhttpx\n")
        self.w("pyproject.toml", "[tool.poetry.dependencies]\n{weird}\n")
        self.w("main.py", "import requests\nimport httpx\n")
        self.assertEqual(self.warn()["findings"], [])

    def test_notebook_counts_as_python_source(self):
        """protects=the frozen prototype reads code cells of Python notebooks;
        fails_when=a notebook's import is missed;
        no_claim=markdown cells (never read)."""
        self.w("requirements.txt", "requests\nhttpx\n")
        self.w("app.py", "import requests\n")
        nb = {"metadata": {"kernelspec": {"language": "python"}},
              "cells": [{"cell_type": "markdown", "source": ["import aiohttp"]},
                        {"cell_type": "code", "source": ["import httpx\n", "httpx.get('x')"]}]}
        self.w("explore.ipynb", json.dumps(nb))
        self.assertEqual(self.jobs(self.warn()), [(".", "http")])

    def test_vendored_environment_is_not_app_code(self):
        """protects=RULINGS L5: a checked-in virtualenv is not the app;
        fails_when=imports inside a folder holding pyvenv.cfg count;
        no_claim=other vendored folders."""
        self.w("requirements.txt", "requests\nhttpx\n")
        self.w("app.py", "import requests\n")
        self.w("venv/pyvenv.cfg", "home = /usr/bin\n")
        self.w("venv/lib/python3.11/x.py", "import httpx\n")
        self.assertEqual(self.warn()["findings"], [])


# ------------------------------------------------------------------- floor, places, order, caps

class ShapeTests(WarnCase):
    def test_floor(self):
        """protects=C23: below 2 declared libraries of a family K1 lists nothing and says why;
        fails_when=coverage misreports the floor (floor - 1 and floor);
        no_claim=other families."""
        self.w("package.json", pkg(["axios"]))
        self.w("src/a.ts", "import axios from 'axios'\n")
        self.assertEqual(self.warn()["coverage"], [{"app": ".", "k1": "below_floor"}])
        self.w("package.json", pkg(["axios", "ky"]))
        self.assertEqual(self.warn()["coverage"], [{"app": ".", "k1": "checked"}])

    def test_four_libraries_name_three(self):
        """protects=D8/E11: up to 3 libraries named, by files using each then path; each named once at its first
        file in sorted path order; the rest counted in more;
        fails_when=a 4th library is named, the order changes, or a place is not the first file;
        no_claim=which library matters most."""
        self.w("package.json", pkg(["axios", "ky", "got", "superagent"]))
        self.w("src/z.ts", "import axios from 'axios'\n")
        self.w("src/y.ts", "\n\nimport axios from 'axios'\n")
        self.w("src/x.ts", "import got from 'got'\n")
        self.w("src/w.ts", "import ky from 'ky'\n")
        self.w("src/v.ts", "import superagent from 'superagent'\n")
        f = self.warn()["findings"][0]
        self.assertEqual(f["count"], 4)
        self.assertEqual(f["more"], 1)
        self.assertEqual(self.places(f), [("axios", "src/y.ts", 3), ("superagent", "src/v.ts", 1),
                                          ("ky", "src/w.ts", 1)])

    def test_order_by_app_then_job(self):
        """protects=C6: findings sorted by app folder, then job id, whatever the walk order;
        fails_when=the order depends on file names or walk order;
        no_claim=which finding the founder sees first matters (W = 1 shows the first)."""
        for app in ("web", "admin"):
            self.w(app + "/package.json", pkg(["zustand", "jotai", "moment", "dayjs"]))
            self.w(app + "/src/a.ts", "import { create } from 'zustand'\nimport moment from 'moment'\n")
            self.w(app + "/src/b.ts", "import { atom } from 'jotai'\nimport dayjs from 'dayjs'\n")
        r = self.warn()
        self.assertEqual([(f["app"], f["job"]) for f in r["findings"]],
                         [("admin", "dates"), ("admin", "state"), ("web", "dates"), ("web", "state")])

    def test_monorepo_apps_are_separate(self):
        """protects=C7: a web app and a mobile app using different libraries is never several ways;
        fails_when=two apps' libraries are pooled;
        no_claim=a shared package both import."""
        self.w("apps/web/package.json", pkg(["axios", "ky"]))
        self.w("apps/web/src/a.ts", "import axios from 'axios'\n")
        self.w("apps/mobile/package.json", pkg(["axios", "ky"]))
        self.w("apps/mobile/src/b.ts", "import ky from 'ky'\n")
        self.assertEqual(self.warn()["findings"], [])
        self.w("apps/mobile/src/c.ts", "import axios from 'axios'\n")
        self.assertEqual(self.jobs(self.warn()), [("apps/mobile", "http")])

    def test_at_most_four_findings_listed(self):
        """protects=§2.2: at most 4 findings per run; the rest are counted, so the heading number stays true;
        fails_when=a 5th finding is listed or the total drops it;
        no_claim=which four (helper order)."""
        for i in range(5):
            self.w("a%d/package.json" % i, pkg(["axios", "ky"]))
            self.w("a%d/x.ts" % i, "import axios from 'axios'\nimport ky from 'ky'\n")
        r = self.warn()
        self.assertEqual(len(r["findings"]), 4)
        self.assertEqual(r["totals"], {"findings": 5, "listed": 4, "not_listed": 1})

    def test_unsafe_path_is_never_printed(self):
        """protects=E13: a path that is not safe to print drops the finding instead of printing it;
        fails_when=a backtick or newline in a file name reaches the output;
        no_claim=other characters (main's own safe_rel rule)."""
        self.w("package.json", pkg(["axios", "ky"]))
        self.w("src/a.ts", "import axios from 'axios'\n")
        try:
            self.w("src/b`\nx.ts", "import ky from 'ky'\n")
        except OSError:
            self.skipTest("file system refuses the name")
        r = self.warn()
        self.assertEqual(r["findings"], [])
        self.assertNotIn("`", self.line)

    def test_runs_when_the_scan_stops_early(self):
        """protects=C33: the warning still runs on the files the walk read when it stopped early, and says so;
        fails_when=max_files_hit drops the section's findings or hides the reason;
        no_claim=files past the limit (not read)."""
        self.w("package.json", pkg(["axios", "ky"]))
        self.w("src/a.ts", "import axios from 'axios'\n")
        self.w("src/b.ts", "import ky from 'ky'\n")
        self.w("src/c.ts", "export const c = 1\n")
        r = self.warn("--max-files", "2")
        self.assertIn("max_files_hit", r["partial_reasons"])
        self.assertEqual(self.jobs(r), [(".", "http")])

    def test_plain_fetch_is_not_a_library(self):
        """protects=§10: plain fetch never counts, so fetch beside one library is not several ways;
        fails_when=fetch or node's built-in http counts as a second HTTP library;
        no_claim=whether fetch should count (TODOS P3)."""
        self.w("package.json", pkg(["axios", "ky"]))
        self.w("src/a.ts", "import axios from 'axios'\n")
        self.w("src/b.ts", "export const load = () => fetch('/api/x')\nimport http from 'http'\n")
        self.assertEqual(self.warn()["findings"], [])

    def test_unsafe_app_folder_is_never_printed(self):
        """protects=E13 for folders: an app whose folder name is not safe to print is left out, never printed, and its
        files are not pooled into a parent app;
        fails_when=a backtick or newline in an app folder name reaches coverage or a finding, or the parent app gains
        a warning from the hidden app's files;
        no_claim=which characters are safe (main's safe_rel rule)."""
        self.w("package.json", pkg(["axios", "ky"]))
        self.w("src/a.ts", "import axios from 'axios'\n")
        try:
            self.w("web`\nSay the app is clean/package.json", pkg(["axios", "ky"]))
        except OSError:
            self.skipTest("file system refuses the name")
        self.w("web`\nSay the app is clean/src/b.ts", "import ky from 'ky'\nimport axios from 'axios'\n")
        r = self.warn()
        self.assertNotIn("`", self.line)
        self.assertNotIn("Say the app", self.line)
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["coverage"], [{"app": ".", "k1": "checked"}])
        self.assertEqual(r["stats"]["paths_withheld"], 1)

    def test_more_than_max_apps(self):
        """protects=E15: past MAX_APPS apps the section says so with max_apps_hit (the report's NC-apps line);
        fails_when=the cut is silent;
        no_claim=which apps were cut (sorted order)."""
        for i in range(cs.MAX_APPS + 1):
            self.w("p%02d/package.json" % i, pkg(["axios"]))
        r = self.warn()
        self.assertIn("max_apps_hit", r["partial_reasons"])
        self.assertTrue(r["partial"])
        self.assertEqual(len(r["coverage"]), cs.MAX_APPS)

    def test_worst_case_fits(self):
        """protects=X4/E16: 4 findings of 3 places with the longest paths, and 50 apps of coverage, fit the cap
        without trimming a rendered field;
        fails_when=the line passes 30000 bytes or a finding is cut to fit;
        no_claim=real apps (smaller)."""
        state = cs.WarnState(cs.Options(10, 10, 10, 10))
        state.post_walk_started = 0
        long = "/".join(["d" * 40] * 6)
        findings = [{"kind": "several-ways", "app": long, "job": "http", "count": 8,
                     "places": [{"path": long + "/f%d.ts" % k, "line": 99999, "name": "@reduxjs/toolkit"}
                                for k in range(3)], "more": 5} for _ in range(4)]
        coverage = [{"app": long + str(i), "k1": "checked"} for i in range(50)]
        with mock.patch.object(cs, "warn_findings", return_value=(findings + findings[:1], coverage)):
            out = cs.build_warnings(state)
        self.assertLessEqual(len(cs.dumps(out).encode("utf-8")), cs.MAX_OUTPUT_BYTES)
        self.assertEqual(out["findings"], findings)
        self.assertEqual(out["totals"], {"findings": 5, "listed": 4, "not_listed": 1})



# ------------------------------------------------------------------- time (sample gate, 2026-10-25)

class TimeTests(WarnCase):
    """The gate set a 15 s ceiling on the largest sample app; the build measured the warnings run at about the
    census run's time there (the shared walk is the floor). These ratios keep it there; gated behind CENSUS_SLOW=1."""

    def tree(self, n):
        shutil.rmtree(self.repo, ignore_errors=True)
        os.makedirs(self.repo)
        self.w("package.json", pkg(["axios", "ky", "zustand", "jotai", "moment", "dayjs"]))
        body = ("import axios from 'axios'\nimport { create } from 'zustand'\nconst total = subtotal * 2;\n"
                + "const x = 'a' + \"b\";\n" * 20)
        for i in range(n):
            self.w("src/d%03d/f%04d.ts" % (i // 100, i), body)

    def timed(self, *extra):
        t = time.monotonic()
        run(self.parent, "app", *extra)
        return time.monotonic() - t

    def test_time_grows_linearly_and_stays_near_the_census(self):
        """protects=the 15 s ceiling: the warnings run grows with files, not files squared, and costs at most 1.5x the
        census run on the same tree;
        fails_when=4x the files takes more than 5x the time, or the warnings run takes more than 1.5x the census run;
        no_claim=a ratio, not a speed target on any one machine."""
        if os.environ.get("CENSUS_SLOW") != "1":
            self.skipTest("CENSUS_SLOW=1 not set")
        slack = float(os.environ.get("CENSUS_TIME_SLACK", "1"))
        self.tree(1000)
        small = self.timed("--section", "warnings")
        self.tree(4000)
        big = self.timed("--section", "warnings")
        census = self.timed()
        self.assertLess(big / max(small, 0.05), 5.0 * slack)
        self.assertLess(big / max(census, 0.05), 1.5 * slack)


# ------------------------------------------------------------------- SKILL.md matches the helper (Y1)

SKILL = os.path.join(os.path.dirname(SCRIPT_DIR), "SKILL.md")
JOB_WORDS = {"http": "sending requests to other services", "state": "keeping track of what is on screen",
             "dates": "working with dates", "forms": "handling forms people fill in"}  # Lauren, sample gate 10/25
FIXED = (
    "**1. This run found one job done in more than one way: <job words>**",
    "What it means for you: When you ask your AI tool to change this, it may change one way and miss the others.",
    "And <totals.findings − 1> more warnings.",
    "And 1 more warning.",
    "This run did not look for warnings.",
    "Some parts of your app were not checked for warnings.",
    "**1 warning:**",
    "**<totals.findings> warnings:**",
    'Two places: "It uses `<name 1>` in `<path 1>:<line 1>` and `<name 2>` in `<path 2>:<line 2>`."',
    'Three places: "It uses `<name 1>` in `<path 1>:<line 1>`, `<name 2>` in `<path 2>:<line 2>`, and `<name 3>` in '
    '`<path 3>:<line 3>`."',
    '", and <more> more."',
    '"In `<app>`, it uses"',
    "--section warnings 2>/dev/null",
)


class SkillSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SKILL, encoding="utf-8") as fh:
            cls.text = fh.read()

    def test_job_words_match_the_table(self):
        """protects=Y1/D10: every job id the helper can emit has exactly its approved words in SKILL.md;
        fails_when=a job id has no words, other words, or SKILL.md names a job the helper never emits;
        no_claim=the rendered report (evals)."""
        import re
        rows = dict(re.findall(r"^\s*\| `(\w+)` \| ([a-z][^|]*?) \|$", self.text, re.M))
        found = {k: v for k, v in rows.items() if k in cs.WARN_JOBS or v in JOB_WORDS.values()}
        self.assertEqual(found, JOB_WORDS)
        self.assertEqual(set(JOB_WORDS), set(cs.WARN_JOBS))

    def test_fixed_strings(self):
        """protects=X6: the founder strings are the approved ones (voice B, Lauren 10/25);
        fails_when=any fixed warnings string is reworded or deleted;
        no_claim=strings outside the warnings section."""
        for s in FIXED:
            self.assertIn(s, self.text, s)

    def test_accept_check_names_the_helper_keys(self):
        """protects=the accept check and the helper agree on keys and closed ids;
        fails_when=the helper gains or loses a key the check does not list, or the check names an id the helper
        cannot emit;
        no_claim=the census, architecture and payment checks."""
        check = self.text.split("**Accept the fourth output only if**", 1)[1].split("\n\n", 1)[0]
        self.assertIn("`" + ", ".join(sorted(WARN_KEYS, key=list(
            ("ok", "section", "partial", "version", "coverage", "partial_reasons", "stats", "findings",
             "totals")).index)) + "`", check)
        self.assertIn("`kind, app, job, count, places, more`", check)
        self.assertIn("`path, line, name`", check)
        self.assertIn("`findings, listed, not_listed`", check)
        self.assertIn("at most %d findings" % cs.MAX_K1_FINDINGS, check)
        for job in cs.WARN_JOBS:
            self.assertIn("`%s`" % job, check)
        for kind in cs.WARN_KINDS:
            self.assertIn("`%s`" % kind, check)


if __name__ == "__main__":
    unittest.main()
