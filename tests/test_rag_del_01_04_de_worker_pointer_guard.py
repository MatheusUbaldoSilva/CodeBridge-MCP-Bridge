"""RAG-DEL-01.04-DE: real Win32 generation read guard, scratch RAG root only."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from rag.runtime.auto_index_worker import _public_generation
from rag.runtime.production_generation_lock import ProductionGenerationBusy


_CHILD_EXCLUSIVE = r"""
from pathlib import Path
import sys
from unittest.mock import patch
from rag.runtime.production_generation_lock import production_generation_lock
root = Path(sys.argv[1])
with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
           return_value=root / "rag_index.sqlite3"):
    with production_generation_lock(exclusive=True, channel="generation"):
        print("LOCKED", flush=True)
        sys.stdin.readline()
"""


class WorkerPointerGuardTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.state = Path(tmp.name) / "CodeBridge" / "rag"
        self.state.mkdir(parents=True)
        self.pointer = self.state / "active-generation.json"
        self.pointer.write_text(
            json.dumps({"schema_version": 1, "generation": "v1_delta_abcdef12345678"}),
            encoding="utf-8",
        )

    def read(self):
        with (
            patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                  return_value=self.state / "rag_index.sqlite3"),
            patch("rag.runtime.status.resolve_rag_sqlite_path",
                  return_value=self.state / "rag_index.sqlite3"),
        ):
            return _public_generation()

    def test_valid_pointer_under_shared_lock(self):
        self.assertEqual(self.read(), "v1_delta_abcdef12345678")
        self.assertTrue((self.state / "production-generation.lock").is_file())

    def test_transition_journal_forbids_worker_start(self):
        (self.state / "production-generation-transition.json").write_text(
            '{"incomplete":true}', encoding="utf-8",
        )
        with self.assertRaisesRegex(RuntimeError, "transition pending"):
            self.read()

    def test_missing_pointer_fails_closed(self):
        self.pointer.unlink()
        with self.assertRaisesRegex(RuntimeError, "cannot verify"):
            self.read()

    def test_untrusted_generation_and_schema_refused(self):
        for generation, version in [
            ("../private", 1), ("", 1), ("valid", 2),
            (None, 1), ("bad space", 1),
        ]:
            self.pointer.write_text(
                json.dumps({"schema_version": version, "generation": generation}),
                encoding="utf-8",
            )
            with self.subTest(generation=generation, version=version):
                with self.assertRaisesRegex(RuntimeError, "invalid"):
                    self.read()

    def test_exclusive_cutover_lock_blocks_worker_read_across_processes(self):
        holder = subprocess.Popen(
            [sys.executable, "-c", _CHILD_EXCLUSIVE, str(self.state)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        try:
            self.assertEqual(holder.stdout.readline().strip(), "LOCKED")
            with self.assertRaises(ProductionGenerationBusy):
                self.read()
        finally:
            if holder.poll() is None:
                try:
                    holder.communicate(input="\n", timeout=5)
                except subprocess.TimeoutExpired:
                    holder.kill()
                    holder.communicate(timeout=5)
        self.assertEqual(self.read(), "v1_delta_abcdef12345678")

    def test_read_only_pointer_never_changes(self):
        original = self.pointer.read_bytes()
        self.read()
        self.assertEqual(self.pointer.read_bytes(), original)