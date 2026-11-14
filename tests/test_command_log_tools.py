"""Ferramenta MCP codebridge_command_log (author_mcp/command_log_tools.py)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "author_mcp"), str(ROOT / "app_rewrite"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import command_log_tools as t  # noqa: E402


class FakeCL:
    def available_days(self):
        return ["2026-11-13", "2026-11-14"]

    def read_day(self, day=None):
        return [
            {"ts": "2026-11-14T09:30:00-03:00", "tipo": "powershell", "exit": 0, "comando": "git status"},
            {"ts": "2026-11-14T09:31:00-03:00", "tipo": "cmd", "exit": 1, "comando": "dir x"},
        ]

    def summarize_day(self, entries):
        return {"total": len(entries), "falhas": 1}

    def render_day(self, entries):
        return "linha1\nlinha2"


class BuildResultTest(unittest.TestCase):
    def test_day(self):
        r = t.build_result(FakeCL(), "day", "2026-11-14")
        self.assertTrue(r["operation_ok"])
        self.assertEqual(r["action"], "day")
        self.assertEqual(r["day"], "2026-11-14")
        self.assertEqual(len(r["entries"]), 2)
        self.assertEqual(r["summary"]["total"], 2)
        self.assertIn("rendered", r)

    def test_list(self):
        r = t.build_result(FakeCL(), "list")
        self.assertEqual(r["action"], "list")
        self.assertIn("2026-11-14", r["days"])

    def test_limit_keeps_last(self):
        r = t.build_result(FakeCL(), "day", "2026-11-14", limit=1)
        self.assertEqual(len(r["entries"]), 1)
        self.assertEqual(r["entries"][0]["tipo"], "cmd")

    def test_invalid_action(self):
        r = t.build_result(FakeCL(), "delete")
        self.assertFalse(r["operation_ok"])
        self.assertIn("invalida", r["error_message"])

    def test_day_default_is_today(self):
        r = t.build_result(FakeCL())
        self.assertRegex(r["day"], r"^\d{4}-\d{2}-\d{2}$")


class RegisterTest(unittest.TestCase):
    def test_register_with_fake_mcp(self):
        try:
            import mcp.types  # noqa: F401
        except Exception:
            self.skipTest("mcp nao instalado neste interpretador")

        class FakeMCP:
            def __init__(self):
                self.tools = {}

            def tool(self, **kw):
                def deco(fn):
                    self.tools[kw["name"]] = fn
                    return fn
                return deco

        mcp = FakeMCP()
        t.register_command_log_tools(mcp, reader=FakeCL())
        self.assertIn("codebridge_command_log", mcp.tools)
        out = mcp.tools["codebridge_command_log"](action="list")
        self.assertEqual(out["action"], "list")


if __name__ == "__main__":
    unittest.main()
