"""SCOPE.md, checked where a machine can check it.

SCOPE.md is the one written record of what custody-check and build-decisions do and don't do (Lauren,
2026-10-21). These tests read the shipped files, not a model's output: the eval graders check real reports.

Run: python3 -m unittest discover -s free-plugin-standard -p '*_test.py' -v
"""
import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

RECOMMENDS = re.compile(r"ship it|patch it|shelve it|get a person|which door|\brecommends\b", re.I)

# Copy that SCOPE.md says must change and that ships in a later release. Each entry names the file, why it is
# still here, and the release that removes it. The test fails when an entry is no longer needed.
NOT_YET = {}  # build-decisions 0.6.0 dropped "which door" (TODOS 2026-10-21); add a file here only while its fix is scheduled


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class ScopeDocTests(unittest.TestCase):
    def test_scope_names_both_plugins_and_its_rules(self):
        scope = read("free-plugin-standard", "SCOPE.md")
        for line in ("## Custody Check", "## Build Decisions", "Never ask what the code should show.",
                     "Say what is broken and what it means for the founder.",
                     "Recommend anything", "Decided by Lauren Townsend."):
            self.assertIn(line, scope, line)
        self.assertRegex(scope, r"Last change: \d{4}-\d{2}-\d{2}\.")

    def test_standard_points_to_scope(self):
        self.assertIn("SCOPE.md", read("free-plugin-standard", "STANDARD.md"))


class NoRecommendationInCopyTests(unittest.TestCase):
    """SCOPE.md: no copy about the plugins says a plugin recommends anything."""

    FILES = ("README.md", ".claude-plugin/marketplace.json", "custody-check/.claude-plugin/plugin.json",
             "custody-check/README.md", "custody-check/skills/custody-check/SKILL.md",
             "build-decisions/.claude-plugin/plugin.json", "build-decisions/README.md",
             "build-decisions/skills/build-decisions/SKILL.md")

    def copy_of(self, path):
        text = read(*path.split("/"))
        if path.endswith(".json"):
            data = json.loads(text)
            items = data.get("plugins", [data])
            return "\n".join(p.get("description", "") for p in items
                             if p.get("name") in ("custody-check", "build-decisions"))
        if path == "README.md":
            return "\n".join(l for l in text.splitlines() if "custody-check" in l or "build-decisions" in l)
        if path.endswith("SKILL.md"):
            return text.split("\n---\n", 1)[0]  # the description the host shows; the body is instructions
        return text

    def test_no_copy_recommends(self):
        for path in self.FILES:
            found = RECOMMENDS.search(self.copy_of(path))
            if path in NOT_YET:
                self.assertIsNotNone(found, "%s is clean now: drop it from NOT_YET (%s)" % (path, NOT_YET[path]))
                continue
            self.assertIsNone(found, "%s: %s" % (path, found and found.group(0)))

    def test_the_pattern_bites(self):
        for line in ("tells you whether to ship it", "Get a person first", "which door your next change takes", "It recommends a fix"):
            self.assertRegex(line, RECOMMENDS)


# SCOPE.md's "no other service, offer or price" rule is checked by .githooks/pre-push against the private terms
# list kept outside this repo: a public test would have to print the words it bans. The custody report's banned
# lines and its question rule are pinned in plain_english_test.py.


if __name__ == "__main__":
    unittest.main()
