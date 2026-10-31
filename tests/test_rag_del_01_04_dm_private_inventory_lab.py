"""RAG-DEL-01.04-DM: scratch-only cooperative private catalog read."""
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import json
import sqlite3
import subprocess
import sys
import threading
import time

from rag.runtime.knowledge_deletion_private_inventory_lab import (
    PrivateInventoryLabError, laboratory_private_inventory_locked,
)


_HOLDER = r"""
from pathlib import Path
from rag.runtime.auto_index_canary import _catalog_mutex
import sys
with _catalog_mutex(Path(sys.argv[1])):
    print("HELD",flush=True)
    sys.stdin.readline()
"""


class PrivateInventoryLabTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.catalog = self.root / "project-indexes.json"
        self.pointer = self.root / "active-generation.json"
        self.pointer.write_text(
            '{"schema_version":1,"generation":"public-untouched"}',
            encoding="utf-8",
        )
        self.db = self.root / "generations" / "private_v1" / "rag_index.sqlite3"
        self.db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("CREATE TABLE rag_documents "
                       "(project_id TEXT,path TEXT,source_type TEXT)")
            cn.executemany("INSERT INTO rag_documents VALUES (?,?,?)", [
                ("private-demo", "docs/alpha.md", "DOCUMENTATION"),
                ("private-demo", "src/main.cpp", "CODE"),
                ("private-demo", "src/main.cpp", "CODE"),
                ("codebridge", "public/secret-file", "TEXT"),
            ])
            cn.commit()
        self.row = {
            "enabled": True, "project_id": "private-demo",
            "generation_directory": str(self.db.parent.resolve()),
            "sqlite_sha256": sha256(self.db.read_bytes()).hexdigest(),
        }
        self.write_catalog()

    def write_catalog(self):
        self.catalog.write_text(json.dumps({
            "schema_version": 1,
            "projects": {"private-demo": self.row},
        }), encoding="utf-8")

    def read(self, **kwargs):
        defaults = {
            "catalog_file": self.catalog, "sqlite_path": self.db,
            "laboratory_mode": True, "operator_approved": True,
        }
        defaults.update(kwargs)
        return laboratory_private_inventory_locked("private-demo", **defaults)

    def test_private_inventory_isolated_and_immutable(self):
        before = self.catalog.read_bytes(), self.db.read_bytes(), self.pointer.read_bytes()
        result = self.read()
        self.assertEqual(result["state"], "LAB_PRIVATE_INVENTORY_READ_ONLY")
        self.assertEqual(result["documents"], [
            {"path": "docs/alpha.md", "count": 1, "type": "DOCUMENTATION"},
            {"path": "src/main.cpp", "count": 2, "type": "CODE"},
        ])
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["operational_use_allowed"])
        self.assertEqual(
            (self.catalog.read_bytes(), self.db.read_bytes(), self.pointer.read_bytes()),
            before,
        )

    def test_changed_sqlite_fingerprint_blocks(self):
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("INSERT INTO rag_documents VALUES ('private-demo','new','TEXT')")
            cn.commit()
        with self.assertRaisesRegex(PrivateInventoryLabError, "fingerprint drift"):
            self.read()

    def test_untrusted_catalog_entry_is_denied(self):
        self.row["generation_directory"] = str(self.root / "other")
        self.write_catalog()
        with self.assertRaisesRegex(PrivateInventoryLabError, "untrusted"):
            self.read()

    def test_pending_deletion_journal_refuses_read(self):
        (self.root / "rag-del-pending.journal.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(PrivateInventoryLabError, "journal"):
            self.read()

    def test_approval_required_before_creating_lab_lock(self):
        for approval, lab in ((False, True), (True, False)):
            with self.assertRaises(PermissionError):
                self.read(operator_approved=approval, laboratory_mode=lab)
        self.assertFalse((self.root / "auto-canary.lock").exists())

    def test_public_project_cannot_use_private_inventory(self):
        with self.assertRaises(PrivateInventoryLabError):
            laboratory_private_inventory_locked(
                "codebridge", catalog_file=self.catalog, sqlite_path=self.db,
                laboratory_mode=True, operator_approved=True,
            )

    def test_catalog_mutex_serializes_reader_against_foreign_process(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", _HOLDER, str(self.root)],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        completed = threading.Event()
        output = []
        def reader():
            try:
                output.append(self.read())
            finally:
                completed.set()
        try:
            self.assertEqual(proc.stdout.readline().strip(), "HELD")
            worker = threading.Thread(target=reader, daemon=True)
            worker.start()
            time.sleep(0.18)
            self.assertFalse(completed.is_set(),
                             "reader cannot bypass catalog lock")
        finally:
            if proc.poll() is None:
                try:
                    proc.communicate(input="\n", timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=5)
        worker.join(timeout=7)
        self.assertTrue(completed.is_set())
        self.assertEqual(output[0]["state"], "LAB_PRIVATE_INVENTORY_READ_ONLY")
        self.assertEqual(proc.returncode, 0)