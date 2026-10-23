"""Tests for the architecture section's value_handlers list (build-decisions 0.6.0, "the browser chooses it").

value_handlers is the read order for the skill's "Who decides each value" step: at most 10 of the server files the
section already lists (own-api-routes, server-actions), those that read the request and name a value (points,
amount, price, date, limit, role, plan, credits ...) first. It is added only in the room the legacy output leaves, so
the shape, facts, candidates and totals main prints never change (plan B1, EV1). F-6 2026-10-22: the helper's
alphabetical order missed a real credits bug at #17 of 25.

Run: python3 -m unittest discover -s build-decisions/skills/build-decisions/scripts -p '*_test.py' -v
"""
import json
import os
import sys
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import census_scan as cs  # noqa: E402
from architecture_test import ArchCase, NEXT_PKG, ROUTE  # noqa: E402

TAKES_POINTS = ("'use server'\n"
                "export async function award(formData) {\n"
                "  const points = Number(formData.get('points'))\n"
                "  await db.insert({ points })\n"
                "}\n")
TAKES_AMOUNT = ("export async function POST(req) {\n"
                "  const { amount } = await req.json()\n"
                "  return Response.json({ amount })\n"
                "}\n")


class ValueHandlersTests(ArchCase):
    def test_value_readers_come_first(self):
        """protects=the read order puts handlers that take a value from the request first; fails_when=the list
        keeps the alphabetical order, so a credits handler at #17 is never read; no_claim=it does not say a
        listed file trusts the value (the agent reads it)."""
        self.w("package.json", NEXT_PKG)
        for i in range(5):
            self.w("app/api/a%d/route.ts" % i, ROUTE)
        self.w("app/api/zz-award/route.ts", TAKES_AMOUNT)
        self.w("app/actions/points.ts", TAKES_POINTS)
        result = self.arch()
        vh = result["value_handlers"]
        self.assertEqual(set(vh[:2]), {"app/api/zz-award/route.ts", "app/actions/points.ts"})
        self.assertEqual(len(vh), 7)

    def test_only_listed_server_paths_at_most_ten(self):
        self.w("package.json", NEXT_PKG)
        for i in range(14):
            self.w("app/api/r%02d/route.ts" % i, ROUTE)
        result = self.arch()
        listed = {s["path"] for s in result["shape"] if s["signal"] in ("own-api-routes", "server-actions")}
        self.assertEqual(len(result["value_handlers"]), 10)
        self.assertTrue(set(result["value_handlers"]) <= listed)
        self.assertEqual(len(set(result["value_handlers"])), 10)

    def test_no_server_files_gives_an_empty_list(self):
        self.w("package.json", NEXT_PKG)
        self.w("app/page.tsx", "export default function Page() { return null }\n")
        self.assertEqual(self.arch().get("value_handlers"), [])

    def test_other_keys_are_unchanged(self):
        """protects=never worse than main: every key main prints is what main would print; fails_when=adding
        the list changes or trims a legacy key."""
        self.w("package.json", NEXT_PKG)
        self.w("app/actions/points.ts", TAKES_POINTS)
        result = self.arch()
        legacy = {k: v for k, v in result.items() if k != "value_handlers"}
        self.assertEqual(cs.add_value_handlers(legacy, ["x"])["shape"], legacy["shape"])
        self.assertEqual(set(result) - {"value_handlers"}, set(legacy))


class RoomRuleTests(unittest.TestCase):
    def big(self, pad):
        return {"ok": True, "section": "architecture", "shape": [{"signal": "own-api-routes", "path": "p" * pad}],
                "totals": {}}

    def test_fits_the_cap_and_never_touches_legacy_keys(self):
        """protects=the 30,000-byte cap and the legacy payload near it; fails_when=value_handlers pushes the line
        over the cap, or something other than value_handlers shrinks."""
        paths = ["app/api/%s/route.ts" % ("x" * 60) for _ in range(10)]
        base = len(cs.dumps(self.big(0)).encode("utf-8"))
        for room in (cs.MAX_OUTPUT_BYTES, 900, 200, 60, 0):
            legacy = self.big(cs.MAX_OUTPUT_BYTES - base - room)
            pad = room
            out = cs.add_value_handlers(legacy, paths)
            self.assertLessEqual(len(cs.dumps(out).encode("utf-8")), cs.MAX_OUTPUT_BYTES, pad)
            self.assertEqual({k: v for k, v in out.items() if k != "value_handlers"}, legacy)
            if "value_handlers" in out:
                self.assertEqual(out["value_handlers"], paths[:len(out["value_handlers"])])

    def test_no_room_leaves_the_key_out(self):
        legacy = self.big(cs.MAX_OUTPUT_BYTES - 40)
        self.assertNotIn("value_handlers", cs.add_value_handlers(legacy, ["a"]))


if __name__ == "__main__":
    unittest.main()
