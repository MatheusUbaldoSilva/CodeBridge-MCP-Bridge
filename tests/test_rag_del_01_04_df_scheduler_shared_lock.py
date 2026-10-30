"""RAG-DEL-01.04-DF: real Windows shared generation lock for scheduler views."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from rag.runtime.incremental_scheduler_public_pointer import (
    inspect_public_pointer_for_scheduler,
)


_CHILD = r"""
from pathlib import Path
import sys
from unittest.mock import patch
from rag.runtime.production_generation_lock import production_generation_lock
state = Path(sys.argv[1])
with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
           return_value=state / "rag_index.sqlite3"):
    with production_generation_lock(exclusive=True, channel="generation"):
        print("LOCKED",flush=True)
        sys.stdin.readline()
"""


class SchedulerGuardTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "CodeBridge" / "rag"
        self.root.mkdir(parents=True)
        self.pointer = self.root / "active-generation.json"
        self.pointer.write_text(
            json.dumps({"schema_version":1,"generation":"v1_delta_1234567890abcd"}),
            encoding="utf-8",
        )

    def inspect(self):
        with (
            patch("rag.runtime.incremental_scheduler_public_pointer.resolve_rag_sqlite_path",
                  return_value=self.root / "rag_index.sqlite3"),
            patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                  return_value=self.root / "rag_index.sqlite3"),
        ):
            return inspect_public_pointer_for_scheduler()

    def test_read_only_scheduler_observation_is_guarded(self):
        original = self.pointer.read_bytes()
        result = self.inspect()
        self.assertEqual(result["generation"], "v1_delta_1234567890abcd")
        self.assertEqual(result["state"], "PUBLIC_POINTER_OBSERVED")
        self.assertFalse(result["safe_to_schedule"])
        self.assertEqual(self.pointer.read_bytes(), original)
        self.assertTrue((self.root / "production-generation.lock").is_file())

    def test_exclusive_cutover_returns_busy_without_reading_pointer(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", _CHILD, str(self.root)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=str(Path(__file__).resolve().parents[1]),
        )
        try:
            self.assertEqual(proc.stdout.readline().strip(), "LOCKED")
            result = self.inspect()
            self.assertEqual(result["state"], "PUBLIC_POINTER_BUSY")
            self.assertIsNone(result["generation"])
            self.assertFalse(result["safe_to_schedule"])
        finally:
            if proc.poll() is None:
                try:
                    proc.communicate(input="\n", timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=5)
        self.assertEqual(self.inspect()["state"], "PUBLIC_POINTER_OBSERVED")

    def test_pending_journal_still_blocks_under_shared_lock(self):
        (self.root / "production-generation-transition.json").write_text(
            "{}", encoding="utf-8",
        )
        result = self.inspect()
        self.assertEqual(result["state"], "PUBLIC_TRANSITION_PENDING")
        self.assertFalse(result["safe_to_schedule"])

    def test_missing_pointer_is_not_permission(self):
        self.pointer.unlink()
        result = self.inspect()
        self.assertEqual(result["state"], "PUBLIC_LEGACY_POINTER")
        self.assertFalse(result["safe_to_schedule"])