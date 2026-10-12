"""Checkpoint MCP tools: save, resume, and session-bound permissions."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "author_mcp"))
from development_checkpoint import DevelopmentCheckpoints
from development_checkpoint_tools import register_development_checkpoint_tools


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, **options):
        def register(func):
            self.tools[options["name"]] = (func, options)
            return func
        return register


class DevelopmentMCPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "checkpoint.sqlite3"
        self.sid = "codebridge_" + "a" * 16
        self.control = {"stage": "NORMAL", "claimed_by_codebridge": True,
                        "request_id": self.sid}
        self.server = FakeMCP()
        register_development_checkpoint_tools(
            self.server, store=DevelopmentCheckpoints(self.file),
            control_reader=lambda: dict(self.control))
        self.save = self.server.tools["codebridge_dev_checkpoint_save"][0]
        self.latest = self.server.tools["codebridge_dev_checkpoint_latest"][0]

    def test_save_and_resume_across_store_instances(self):
        first = self.save("stage done", "run tests", ["created"], ["audit"])
        self.assertEqual(first["state"], "CHECKPOINT_SAVED")
        self.assertEqual(first["checkpoint"]["revision"], 1)
        recovered = DevelopmentCheckpoints(self.file).latest(self.sid)
        self.assertEqual(recovered["next_step"], "run tests")
        self.control["stage"] = "WRAP_UP_NOW"
        second = self.save("wrap up", "commit")
        self.assertEqual(second["checkpoint"]["revision"], 2)
        self.assertEqual(second["checkpoint"]["stage"], "WRAP_UP_NOW")
        self.assertEqual(self.latest()["checkpoint"]["revision"], 2)

    def test_rejects_unclaimed_or_inactive(self):
        for control in (
            {"stage": "NORMAL", "claimed_by_codebridge": False, "request_id": self.sid},
            {"stage": "INACTIVE", "claimed_by_codebridge": True, "request_id": self.sid},
            {"stage": "NORMAL", "claimed_by_codebridge": True, "request_id": "invalid"},
        ):
            self.control = control
            with self.assertRaises((RuntimeError, ValueError)):
                self.save("a", "b")
        self.assertFalse(self.file.exists())

    def test_latest_read_only_and_absent(self):
        self.assertEqual(self.latest()["state"], "NO_CHECKPOINT")
        self.assertFalse(self.file.exists())
        with self.assertRaises(ValueError):
            self.latest("unsafe")

    def test_metadata_is_correct(self):
        save = self.server.tools["codebridge_dev_checkpoint_save"][1]
        read = self.server.tools["codebridge_dev_checkpoint_latest"][1]
        self.assertFalse(save["annotations"].read_only_hint)
        self.assertTrue(read["annotations"].read_only_hint)


if __name__ == "__main__":
    unittest.main()
