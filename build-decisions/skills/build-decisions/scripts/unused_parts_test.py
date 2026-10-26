"""Tests for the unused-parts warning in census_scan.py --section warnings (python 3.9, unittest only).

0.8.0 adds the second kind of warning (S-070 K3): runtime packages a JavaScript app lists in package.json that
nothing in the app uses. Ported from the frozen round-4 prototype's tests (S-059/S-070 sample folder,
warnings_proto_test.py); the rules they test passed the F-6 sample on 55 fresh JavaScript apps. Every test docstring
carries its card: protects / fails_when / no_claim. Trees are built at test time in a temporary folder.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import census_scan as cs  # noqa: E402
from census_scan_test import run, write  # noqa: E402

LOCK = json.dumps({"lockfileVersion": 3, "packages": {"": {}}})
K3_PLACE_KEYS = {"path", "line", "name"}
K3_FINDING_KEYS = {"kind", "app", "count", "places", "more"}


def pkg(deps=None, dev=None, scripts=None, **extra):
    d = {"name": "app", "dependencies": deps or {}, "devDependencies": dev or {}}
    if scripts:
        d["scripts"] = scripts
    d.update(extra)
    return json.dumps(d, indent=2)


VITE = {"vite": "5", "react": "18", "react-dom": "18"}


class K3Case(unittest.TestCase):
    def setUp(self):
        self.parent = tempfile.mkdtemp(prefix="k3-test-")

    def tearDown(self):
        shutil.rmtree(self.parent, ignore_errors=True)

    def run_tree(self, tree, *extra, lock=True):
        """Build tree under <parent>/app and run the warnings section. A package-lock.json is added when the tree
        has a package.json and no lockfile, since K3 needs one (round 4)."""
        if lock and "package.json" in tree and not any(
                k.endswith(("package-lock.json", "pnpm-lock.yaml", "yarn.lock")) for k in tree):
            tree = dict(tree, **{"package-lock.json": LOCK})
        app = os.path.join(self.parent, "app")
        shutil.rmtree(app, ignore_errors=True)
        os.makedirs(app)
        for rel, text in tree.items():
            write(app, rel, text)
        result, self.line, _ = run(self.parent, "app", "--section", "warnings", *extra)
        self.assertTrue(result["ok"], result)
        return result

    def k3(self, out, app=None):
        return [f for f in out["findings"] if f["kind"] == "unused-parts" and (app is None or f["app"] == app)]

    def names(self, out, app=None):
        return sorted(p["name"] for f in self.k3(out, app) for p in f["places"])

    def k3_state(self, out):
        return [c["k3"] for c in out["coverage"]]


# ------------------------------------------------------------------- contract

class ContractTests(K3Case):
    def test_finding_shape(self):
        """protects=the skill's accept check for the new kind (exact keys, no job id, places with a line);
        fails_when=an unused-parts finding gains or loses a key, or a place has no line;
        no_claim=the founder wording (SKILL.md)."""
        out = self.run_tree({"package.json": pkg({"react": "18", "react-dom": "18", "a": "1", "b": "1", "c": "1"}),
                             "src/main.tsx": "import 'react'\nimport 'react-dom/client'\n"})
        f = self.k3(out)[0]
        self.assertEqual(set(f), K3_FINDING_KEYS)
        self.assertEqual((f["app"], f["count"], f["more"]), (".", 3, 0))
        for p in f["places"]:
            self.assertEqual(set(p), K3_PLACE_KEYS)
            self.assertEqual(p["path"], "package.json")
            self.assertIsInstance(p["line"], int)
        self.assertEqual(set(out["totals"]), {"findings", "listed", "not_listed"})

    def test_coverage_names_k3_state(self):
        """protects=the Not checked lines (the skill reads coverage[].k3);
        fails_when=a coverage entry has no k3 field or a value outside the closed list;
        no_claim=which value each app gets (the tests below)."""
        out = self.run_tree({"package.json": pkg(VITE), "src/main.tsx": "import 'react'\n"})
        for c in out["coverage"]:
            self.assertIn(c["k3"], cs.WARN_K3_STATES)

    def test_unused_listed_with_line(self):
        """protects=the place a founder can open: package.json and the line of the listed name;
        fails_when=the line is not the dependency's own line;
        no_claim=devDependencies (never listed)."""
        deps = {"react": "18", "react-dom": "18", "moment": "2", "lodash": "4", "zod": "3"}
        t = {"package.json": pkg(deps), "src/main.tsx": "import React from 'react'\nimport { createRoot } from 'react-dom/client'\n",
             "src/a.ts": "import _ from 'lodash'\nimport { z } from 'zod'\n"}
        f = self.k3(self.run_tree(t))[0]
        self.assertEqual(f["places"], [{"path": "package.json", "line": 6, "name": "moment"}])
        self.assertEqual(t["package.json"].split("\n")[5].strip()[:8], '"moment"')

    def test_places_capped_at_three(self):
        """protects=the report's length: at most 3 places, the rest counted in more;
        fails_when=a fourth place is printed or more is wrong;
        no_claim=--uncapped (sample runs only)."""
        deps = {"react": "18", "a": "1", "b": "1", "c": "1", "d": "1", "e": "1"}
        out = self.run_tree({"package.json": pkg(deps), "src/main.tsx": "import 'react'\n"})
        f = self.k3(out)[0]
        self.assertEqual(([p["name"] for p in f["places"]], f["count"], f["more"]), (["a", "b", "c"], 5, 2))
        out = self.run_tree({"package.json": pkg(deps), "src/main.tsx": "import 'react'\n"}, "--uncapped")
        self.assertEqual(len(self.k3(out)[0]["places"]), 5)


# ------------------------------------------------------------------- what counts as used

class UsedTests(K3Case):
    def test_config_css_scripts_pairs_types(self):
        """protects=packages a tool, stylesheet, script or pair uses are never listed (C37, E9);
        fails_when=any of these is listed;
        no_claim=tools named nowhere in the app."""
        deps = {"next": "14", "react": "18", "react-dom": "18", "tailwindcss-animate": "1", "@fontsource/inter": "5",
                "prisma": "5", "@prisma/client": "5", "@types/node": "20", "sharp": "0", "ui": "workspace:*"}
        t = {"package.json": pkg(deps, scripts={"postinstall": "prisma generate", "dev": "next dev"}),
             "tailwind.config.ts": "export default { plugins: [require('tailwindcss-animate')] }\n",
             "app/globals.css": "@import '@fontsource/inter';\n@tailwind base;\n",
             "app/page.tsx": "import React from 'react'\nimport { PrismaClient } from '@prisma/client'\n"}
        self.assertEqual(self.k3(self.run_tree(t)), [])

    def test_floor(self):
        """protects=C23: below 5 runtime packages K3 lists nothing;
        fails_when=a 4-package app gets a warning, or a 5-package app with 3 unused gets none;
        no_claim=devDependencies (not counted)."""
        deps = {"react": "18", "react-dom": "18", "a-pkg": "1", "b-pkg": "1"}
        t = {"package.json": pkg(deps), "src/main.tsx": "import React from 'react'\nimport { createRoot } from 'react-dom/client'\n"}
        out = self.run_tree(t)
        self.assertEqual((self.k3(out), self.k3_state(out)), ([], ["below_floor"]))
        deps["c-pkg"] = "1"
        t["package.json"] = pkg(deps)
        self.assertEqual(self.k3(self.run_tree(t))[0]["count"], 3)

    def test_dev_dependencies_never_listed(self):
        """protects=TD1: only runtime packages are candidates;
        fails_when=a devDependency is listed;
        no_claim=whether dev tools are used."""
        t = {"package.json": pkg(VITE, {"eslint": "9", "a": "1", "b": "1", "c": "1", "d": "1"}),
             "src/main.tsx": "import 'react'\nimport 'react-dom/client'\n"}
        self.assertEqual(self.k3(self.run_tree(t)), [])

    def test_npm_alias_and_bad_name(self):
        """protects=C51/C52: an npm alias is used by its own name; a name that fails the npm rule is never printed;
        fails_when=the alias is listed, or the bad name appears anywhere in the output;
        no_claim=other alias forms."""
        deps = dict(VITE, x="npm:real@1", **{"Bad Name": "1", "q-pkg": "1", "r-pkg": "1"})
        t = {"package.json": pkg(deps), "src/main.tsx": "import 'react'\nimport 'react-dom/client'\n",
             "src/a.ts": "import x from 'x'\n"}
        out = self.run_tree(t)
        self.assertNotIn("x", self.names(out))
        self.assertNotIn("Bad Name", json.dumps(out))
        self.assertEqual(out["stats"]["names_withheld"], 1)

    def test_workspace_and_local_packages_never_listed(self):
        """protects=C52: workspace:, file: and link: packages are the repo's own code, never candidates;
        fails_when=one of them is listed;
        no_claim=published packages."""
        deps = dict(VITE, a="workspace:*", b="file:../b", c="link:../c", d="1", e="1", f="1")
        out = self.run_tree({"package.json": pkg(deps), "src/main.tsx": "import 'react'\nimport 'react-dom/client'\n"},
                            "--uncapped")
        self.assertEqual(self.names(out), ["d", "e", "f", "vite"])

    def test_test_files_count_as_uses(self):
        """protects=§2.4 used set: a package imported only by a test is used (tests are skipped by the census,
        not by K3);
        fails_when=a package a test imports is listed;
        no_claim=K1, where tests never count."""
        deps = dict(VITE, msw="2", a="1", b="1", c="1")
        t = {"package.json": pkg(deps), "src/main.tsx": "import 'react'\nimport 'react-dom/client'\n",
             "src/api.test.ts": "import { setupServer } from 'msw/node'\n"}
        self.assertNotIn("msw", self.names(self.run_tree(t)))

    def test_mdx_import_counts(self):
        """protects=R10/L2: an .mdx page's import is a use;
        fails_when=a package imported only by an .mdx page is listed;
        no_claim=K1 (.mdx is never a K1 place)."""
        deps = dict(VITE, recharts="2", a="1", b="1", c="1")
        t = {"package.json": pkg(deps), "src/main.tsx": "import 'react'\nimport 'react-dom/client'\n",
             "content/intro.mdx": "import { LineChart } from 'recharts'\n\n# Hi\n"}
        self.assertNotIn("recharts", self.names(self.run_tree(t)))

    def test_commented_import_is_not_a_use(self):
        """protects=round 2: a line comment never counts as a use;
        fails_when=a package named only in a // comment is treated as used;
        no_claim=block comments (known gap, TODOS)."""
        deps = dict(VITE, dayjs="1", a="1", b="1")
        t = {"package.json": pkg(deps), "src/main.tsx": "import 'react'\nimport 'react-dom/client'\n// import dayjs from 'dayjs'\n"}
        self.assertIn("dayjs", self.names(self.run_tree(t), "."))

    def test_sass_eslint_pairs_and_makefile(self):
        """protects=dev slice tuning: .scss means sass, an ESLint config means eslint, a pair, a Makefile mention;
        fails_when=any of these is listed;
        no_claim=other tools."""
        deps = {"react": "18", "react-dom": "18", "sass": "1", "eslint": "8", "@supabase/supabase-js": "2",
                "@supabase/ssr": "0", "black": "1", "zod": "3"}
        t = {"package.json": pkg(deps), "src/main.tsx": "import 'react'\nimport 'react-dom/client'\nimport './a.scss'\n"
             "import { createServerClient } from '@supabase/ssr'\n", "src/a.scss": "a{}\n",
             ".eslintrc.json": "{}\n", "Makefile": "fmt:\n\tblack .\n"}
        self.assertEqual(self.names(self.run_tree(t)), ["zod"])

    def test_angular_json_mention(self):
        """protects=E9 read list: a package named in angular.json is used;
        fails_when=it is listed;
        no_claim=other config files."""
        t = {"package.json": pkg({"@angular/core": "17", "apexcharts": "3", "a": "1", "b": "1", "c": "1"}),
             "angular.json": json.dumps({"projects": {"x": {"architect": {"build": {"options": {
                 "allowedCommonJsDependencies": ["apexcharts"]}}}}}}),
             "src/main.ts": "import '@angular/core'\n"}
        self.assertEqual(self.names(self.run_tree(t)), ["a", "b", "c"])

    def test_outside_folder_import(self):
        """protects=round 2: imports followed out of the app folder count (a shared folder via a tsconfig alias);
        fails_when=a package only the shared file imports is listed;
        no_claim=imports that cannot be resolved."""
        t = {"web/package.json": pkg({"react": "1", "zod": "3", "a": "1", "b": "1", "c": "1"}),
             "web/tsconfig.json": '{"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["../*"]}}}',
             "web/src/main.ts": "import 'react'\nimport { s } from '@/shared/schema'\n",
             "shared/schema.ts": "import { z } from 'zod'\nexport const s = z\n", "web/package-lock.json": LOCK}
        self.assertEqual(self.names(self.run_tree(t), "web"), ["a", "b", "c"])

    def test_workspace_dependency_imports_count(self):
        """protects=dev slice postcheck: what a workspace package this app depends on imports counts here too;
        fails_when=tippy.js (imported by @acme/ui only) is listed for apps/web;
        no_claim=workspace packages the app does not list."""
        t = {"package.json": pkg(workspaces=["apps/*", "packages/*"]),
             "packages/ui/package.json": json.dumps({"name": "@acme/ui", "dependencies": {"tippy.js": "6"}}),
             "packages/ui/src/index.ts": "import tippy from 'tippy.js'\nexport const t = tippy\n",
             "apps/web/package.json": pkg({"react": "1", "@acme/ui": "workspace:*", "tippy.js": "6", "a": "1",
                                           "b": "1", "c": "1"}),
             "apps/web/x.ts": "import 'react'\nimport { t } from '@acme/ui'\n"}
        self.assertEqual(self.names(self.run_tree(t), "apps/web"), ["a", "b", "c"])


# ------------------------------------------------------------------- lockfiles (round 2 and round 4)

class LockfileTests(K3Case):
    def base(self):
        return {"package.json": pkg({"react": "18", "recharts": "2", "react-is": "18", "a": "1", "b": "1"}),
                "src/main.tsx": "import 'react'\nimport { LineChart } from 'recharts'\n"}

    def test_package_lock_dependency(self):
        """protects=round 2: a package a used package depends on (package-lock.json) is used;
        fails_when=react-is is listed;
        no_claim=packages nothing used depends on."""
        t = self.base()
        t["package-lock.json"] = json.dumps({"lockfileVersion": 3, "packages": {
            "": {"dependencies": {"recharts": "2"}},
            "node_modules/recharts": {"version": "2.1", "dependencies": {"react-is": "^18"}},
            "node_modules/react-is": {"version": "18.0.0"}}})
        self.assertEqual(self.names(self.run_tree(t)), ["a", "b"])

    def test_pnpm_lock_peer(self):
        """protects=round 2: a peer named in pnpm-lock.yaml is used;
        fails_when=react-is is listed;
        no_claim=other pnpm lock layouts."""
        t = self.base()
        t["pnpm-lock.yaml"] = ("lockfileVersion: '9.0'\n\npackages:\n\n  recharts@2.1.0:\n"
                               "    resolution: {integrity: x}\n    peerDependencies:\n      react-is: ^18\n\n"
                               "snapshots:\n\n  recharts@2.1.0(react-is@18.0.0):\n    dependencies:\n"
                               "      react-is: 18.0.0\n")
        self.assertEqual(self.names(self.run_tree(t)), ["a", "b"])

    def test_yarn_lock_dependency(self):
        """protects=round 2: a dependency in yarn.lock is used;
        fails_when=react-is is listed;
        no_claim=yarn berry quirks beyond this shape."""
        t = self.base()
        t["yarn.lock"] = ('# yarn lockfile v1\n\n"recharts@^2":\n  version "2.1.0"\n  dependencies:\n'
                          '    react-is "^18"\n\nreact-is@^18:\n  version "18.0.0"\n')
        self.assertEqual(self.names(self.run_tree(t)), ["a", "b"])

    def test_no_lockfile_is_quiet(self):
        """protects=round 4: with no readable lockfile K3 stays quiet and says why (no_lockfile);
        fails_when=a warning is printed, or coverage says anything else;
        no_claim=below-floor apps (below_floor wins)."""
        t = {"package.json": pkg({"react": "18", "react-dom": "18", "a-pkg": "1", "b-pkg": "1", "c-pkg": "1"}),
             "src/main.tsx": "import 'react'\nimport 'react-dom/client'\n"}
        out = self.run_tree(t, lock=False)
        self.assertEqual((self.k3(out), self.k3_state(out)), ([], ["no_lockfile"]))

    def test_bun_lockfile_only_is_quiet(self):
        """protects=round 4: Bun lockfiles are not read yet, so a Bun-only app is no_lockfile;
        fails_when=a warning is printed;
        no_claim=Bun support (a later item)."""
        t = {"package.json": pkg({"react": "18", "react-dom": "18", "a-pkg": "1", "b-pkg": "1", "c-pkg": "1"}),
             "src/main.tsx": "import 'react'\nimport 'react-dom/client'\n", "bun.lockb": "binary"}
        out = self.run_tree(t, lock=False)
        self.assertEqual((self.k3(out), self.k3_state(out)), ([], ["no_lockfile"]))

    def test_lockfile_in_parent_folder_counts(self):
        """protects=round 4: a lockfile in a folder above the app covers it (monorepo root lockfile);
        fails_when=the app is no_lockfile;
        no_claim=lockfiles in sibling folders."""
        t = {"package-lock.json": LOCK,
             "web/package.json": pkg({"react": "18", "react-dom": "18", "a-pkg": "1", "b-pkg": "1", "c-pkg": "1"}),
             "web/src/main.tsx": "import 'react'\nimport 'react-dom/client'\n"}
        self.assertEqual(self.names(self.run_tree(t, lock=False), "web"), ["a-pkg", "b-pkg", "c-pkg"])

    def test_empty_lockfile_counts_as_read(self):
        """protects=round 4 'readable' as the sample ran it: an empty or unparsable but readable lockfile covers
        the app (its graph is empty, so nothing extra counts as used);
        fails_when=the app is no_lockfile;
        no_claim=lockfiles over MAX_LOCKFILE_BYTES (read as none; the cap is checked here)."""
        t = {"package.json": pkg({"react": "18", "react-dom": "18", "a-pkg": "1", "b-pkg": "1", "c-pkg": "1"}),
             "src/main.tsx": "import 'react'\nimport 'react-dom/client'\n", "yarn.lock": ""}
        out = self.run_tree(t, lock=False)
        self.assertEqual(self.k3_state(out), ["checked"])
        self.assertEqual(cs.MAX_LOCKFILE_BYTES, 32 * 1024 * 1024)


# ------------------------------------------------------------------- S-070 fixes (round 3) and round 4 rules

class S070Tests(K3Case):
    BASE = {"react": "18", "react-dom": "18", "a-pkg": "1", "b-pkg": "1", "c-pkg": "1"}

    def app(self, extra, scripts=None, **files):
        t = {"package.json": pkg(dict(self.BASE, **extra), scripts=scripts),
             "src/main.tsx": "import 'react'\nimport 'react-dom/client'\n"}
        t.update(files)
        return t

    def all_names(self, t):
        return self.names(self.run_tree(t, "--uncapped"))

    def test_node_modules_path_in_tailwind_css_gradle(self):
        """protects=S-070 cause 1: node_modules/<pkg> paths in a config, CSS or Gradle file are uses;
        fails_when=flowbite-react, geist or @capacitor/android is listed;
        no_claim=paths in other file kinds."""
        t = self.app({"flowbite-react": "1", "geist": "1", "@capacitor/android": "8"},
                     **{"tailwind.config.js": "module.exports = { content: ['./node_modules/flowbite-react/**/*.js'] }\n",
                        "src/index.css": "@font-face { src: url('../node_modules/geist/dist/a.woff2') }\n",
                        "android/capacitor.settings.gradle":
                            "project(':capacitor-android').projectDir = new File('../node_modules/@capacitor/android/capacitor')\n"})
        self.assertEqual(self.all_names(t), ["a-pkg", "b-pkg", "c-pkg"])

    def test_lockfile_followed_from_config_used_package(self):
        """protects=S-070: lockfile needs are followed from packages found in a config, to a fixed point;
        fails_when=classnames or flowbite is listed;
        no_claim=packages nothing used needs."""
        lock = {"lockfileVersion": 3, "packages": {"": {}, "node_modules/flowbite-react": {
            "dependencies": {"classnames": "^2"}, "peerDependencies": {"flowbite": "^1"}}}}
        t = self.app({"flowbite-react": "1", "classnames": "2", "flowbite": "1"},
                     **{"tailwind.config.js": "module.exports = { content: ['./node_modules/flowbite-react/**/*.js'] }\n",
                        "package-lock.json": json.dumps(lock)})
        self.assertEqual(self.all_names(t), ["a-pkg", "b-pkg", "c-pkg"])

    def test_orm_loads_its_driver(self):
        """protects=S-070 cause 2: a driver or helper an ORM loads by itself is used when the ORM is;
        fails_when=pg-hstore is listed next to sequelize, or not listed without it;
        no_claim=ORMs outside PAIRED_WITH."""
        t = self.app({"sequelize": "6", "pg": "8", "pg-hstore": "2"}, **{"src/db.ts": "import { Sequelize } from 'sequelize'\n"})
        self.assertEqual(self.all_names(t), ["a-pkg", "b-pkg", "c-pkg"])
        self.assertIn("pg-hstore", self.all_names(self.app({"pg-hstore": "2"})))

    def test_expo_autolinks_expo_modules(self):
        """protects=S-070 cause 3: Expo autolinks every expo-* module the app lists;
        fails_when=expo-system-ui is listed with expo used, or not listed without expo;
        no_claim=other autolinking tools."""
        t = self.app({"expo": "51", "expo-system-ui": "3"}, scripts={"start": "expo start"})
        self.assertEqual(self.all_names(t), ["a-pkg", "b-pkg", "c-pkg"])
        self.assertIn("expo-system-ui", self.all_names(self.app({"expo-system-ui": "3"})))

    def test_eslint_scoped_plugin_and_next_shorthand(self):
        """protects=S-070 cause 4: ESLint names plugins and configs by shorthand (next/typescript, @x/rule);
        fails_when=eslint-config-next or @typescript-eslint/* is listed;
        no_claim=a scoped plugin nothing names (still listed)."""
        lock = {"lockfileVersion": 3, "packages": {"": {}, "node_modules/eslint-config-next": {
            "dependencies": {"@typescript-eslint/parser": "^8"}}}}
        t = self.app({"eslint-config-next": "15", "@typescript-eslint/eslint-plugin": "8", "@typescript-eslint/parser": "8"},
                     **{".eslintrc.json": json.dumps({"extends": ["next/core-web-vitals", "next/typescript"],
                                                      "rules": {"@typescript-eslint/no-unused-vars": "warn"}}),
                        "package-lock.json": json.dumps(lock)})
        self.assertEqual(self.all_names(t), ["a-pkg", "b-pkg", "c-pkg"])
        self.assertIn("@typescript-eslint/eslint-plugin", self.all_names(self.app({"@typescript-eslint/eslint-plugin": "8"})))

    def test_escaped_node_modules_path_in_vite_config(self):
        """protects=round 4: an escaped node_modules\\/ path (Vite manualChunks regex) is a use;
        fails_when=zod or @hookform/resolvers is listed;
        no_claim=other regex shapes."""
        t = self.app({"zod": "3", "@hookform/resolvers": "3"},
                     **{"vite.config.ts": "export default { build: { rollupOptions: { output: { manualChunks(id) {"
                                          " if (/node_modules\\/zod(\\/|$)/.test(id)) return 'z';"
                                          " if (/node_modules\\/@hookform\\/resolvers/.test(id)) return 'f' } } } } }\n"})
        self.assertEqual(self.all_names(t), ["a-pkg", "b-pkg", "c-pkg"])

    def test_tool_settings_file_counts(self):
        """protects=round 4: a tool's own settings file (.xrc, .xignore, x.config.*, x/config.toml) makes x used;
        fails_when=jshint or supabase is listed, or firebase (whose firebase.json is the CLI's) is not;
        no_claim=settings files with other names."""
        deps = {"react": "18", "a-pkg": "1", "b-pkg": "1", "c-pkg": "1", "jshint": "2", "supabase": "1", "firebase": "10"}
        t = {"package.json": pkg(deps), "src/main.tsx": "import 'react'\n", ".jshintignore": "dist\n",
             "supabase/config.toml": "project_id = 'x'\n", "firebase.json": "{}"}
        self.assertEqual(self.all_names(t), ["a-pkg", "b-pkg", "c-pkg", "firebase"])


# ------------------------------------------------------------------- skips (C32, C33, X1) and Python

class SkipTests(K3Case):
    def test_malformed_manifest(self):
        """protects=X1: an unreadable package.json skips K3 and says why;
        fails_when=coverage is not manifest_unreadable or the partial reason is missing;
        no_claim=Python manifests (Python K3 is cut)."""
        out = self.run_tree({"package.json": "{ not json", "src/a.ts": "x\n"}, lock=False)
        self.assertEqual(self.k3_state(out), ["manifest_unreadable"])
        self.assertIn("manifest_unreadable", out["partial_reasons"])

    def test_unread_file_skips_k3(self):
        """protects=C33: a file the walk could not read (here: oversize) skips K3 for its app;
        fails_when=K3 still lists packages the unread file may use;
        no_claim=K1 (still runs)."""
        t = {"package.json": pkg({"react": "18", "react-dom": "18", "a-pkg": "1", "b-pkg": "1", "c-pkg": "1"}),
             "src/main.tsx": "import 'react'\nimport 'react-dom/client'\n", "src/big.ts": "// x\n" * 200000}
        out = self.run_tree(t)
        self.assertEqual((self.k3(out), self.k3_state(out)), ([], ["files_unread"]))

    def test_python_is_cut(self):
        """protects=round 2: Python K3 is cut (no lockfile shows what a library pulls in);
        fails_when=a Python app gets an unused-parts warning or a Not checked state;
        no_claim=a later Python release."""
        t = {"requirements.txt": "flask\nrich\ntyper\npandas\nnltk\n", "app.py": "import flask\n"}
        out = self.run_tree(t)
        self.assertEqual((self.k3(out), self.k3_state(out)), ([], ["below_floor"]))
        out = self.run_tree({"pyproject.toml": "[tool.poetry.dependencies]\n[[weird\n", "app.py": "import flask\n"})
        self.assertNotIn("manifest_unreadable", out["partial_reasons"])


# ------------------------------------------------------------------- output order and caps

class OutputTests(K3Case):
    def test_order_and_cap(self):
        """protects=C6/C7: findings sorted by kind, then app folder; at most 6 listed, all counted in totals;
        fails_when=order or the cap differs;
        no_claim=the report (it shows one block, W = 1)."""
        t = {"package.json": pkg(workspaces=["apps/*"])}
        for a in ("b", "a", "c", "d", "e", "f", "g"):
            t[f"apps/{a}/package.json"] = pkg({"react": "1", "p1": "1", "p2": "1", "p3": "1", "p4": "1"})
            t[f"apps/{a}/x.ts"] = "import 'react'\n"
        out = self.run_tree(t)
        self.assertEqual((out["totals"]["findings"], out["totals"]["listed"], out["totals"]["not_listed"]), (7, 6, 1))
        self.assertEqual([f["app"] for f in out["findings"]], ["apps/a", "apps/b", "apps/c", "apps/d", "apps/e", "apps/f"])

    def test_several_ways_first(self):
        """protects=C6: several-ways findings come before unused-parts;
        fails_when=an unused-parts finding is listed first;
        no_claim=K1's own order (warnings_test)."""
        deps = {"react": "18", "axios": "1", "ky": "1", "a": "1", "b": "1"}
        t = {"package.json": pkg(deps), "src/a.ts": "import axios from 'axios'\nimport 'react'\n",
             "src/b.ts": "import ky from 'ky'\n"}
        out = self.run_tree(t)
        self.assertEqual([f["kind"] for f in out["findings"]], ["several-ways", "unused-parts"])
        self.assertEqual(out["totals"]["findings"], 2)

    def test_worst_case_fits(self):
        """protects=X4/E16: 6 findings of 3 places with the longest allowed paths and 50 apps of coverage stay
        under the 30000-byte cap without trimming anything rendered;
        fails_when=the line is over the cap;
        no_claim=more than 50 apps (max_apps_hit)."""
        long = "x" * 60
        t = {"package.json": pkg(workspaces=["%s/*" % long])}
        for i in range(50):
            d = "%s/%s%02d/%s" % (long, long[:50], i, long[:60])
            t["%s/package.json" % d] = pkg({"react": "1", "p1-%s" % long[:40]: "1", "p2-%s" % long[:40]: "1",
                                            "p3-%s" % long[:40]: "1", "p4-%s" % long[:40]: "1"})
            t["%s/x.ts" % d] = "import 'react'\n"
        out = self.run_tree(t)
        self.assertLessEqual(len(self.line.encode("utf-8")), cs.MAX_OUTPUT_BYTES)
        self.assertEqual(len(out["findings"]), 6)
        self.assertEqual(len(out["coverage"]), 50)


if __name__ == "__main__":
    unittest.main()
