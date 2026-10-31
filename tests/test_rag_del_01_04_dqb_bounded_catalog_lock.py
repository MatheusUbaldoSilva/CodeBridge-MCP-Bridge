"""RAG-DEL-01.04-DQ-B: real Windows catalog mutex, bounded and scratch-only."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import subprocess
import sys
import time

from rag.runtime.auto_index_canary import _catalog_mutex
from rag.runtime.knowledge_deletion_bounded_catalog_lab import (
    bounded_catalog_mutex_lab, LaboratoryCatalogBusy, LaboratoryCatalogUnsafe,
)


_CHILD = r"""
import sys
from pathlib import Path
from rag.runtime.auto_index_canary import _catalog_mutex
with _catalog_mutex(Path(sys.argv[1])):
    print("HELD",flush=True)
    sys.stdin.readline()
"""


class BoundedCatalogLabTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.catalog = self.root / "project-indexes.json"
        self.catalog.write_text(
            '{"schema_version":1,"projects":{}}', encoding="utf-8",
        )

    def acquire(self, *, timeout=0.25, **kwargs):
        return bounded_catalog_mutex_lab(
            self.catalog, timeout_seconds=timeout,
            laboratory_mode=True, operator_approved=True, **kwargs,
        )

    def test_success_releases_and_only_creates_scratch_lock(self):
        original = self.catalog.read_bytes()
        with self.acquire() as catalog:
            self.assertEqual(catalog, self.catalog)
            self.assertTrue((self.root / "auto-canary.lock").is_file())
        with self.acquire():
            pass
        self.assertEqual(self.catalog.read_bytes(), original)

    def test_real_writer_lock_times_out_nonblocking(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", _CHILD, str(self.root)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        try:
            self.assertEqual(proc.stdout.readline().strip(), "HELD")
            start = time.monotonic()
            with self.assertRaises(LaboratoryCatalogBusy):
                with self.acquire(timeout=0.07):
                    self.fail("reader may not bypass writer lock")
            elapsed = time.monotonic()-start
            self.assertLess(elapsed, 0.75)
        finally:
            if proc.poll() is None:
                try:
                    proc.communicate(input="\n",timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=5)
        self.assertEqual(proc.returncode,0)
        with self.acquire(timeout=0.2):
            pass

    def test_exception_does_not_leak_lock(self):
        with self.assertRaisesRegex(RuntimeError, "boom"):
            with self.acquire():
                raise RuntimeError("boom")
        with _catalog_mutex(self.root):
            pass

    def test_unapproved_no_lock_file_created(self):
        for approved, lab in ((False,True),(True,False)):
            with self.assertRaises(PermissionError):
                with bounded_catalog_mutex_lab(
                    self.catalog, laboratory_mode=lab,
                    operator_approved=approved,
                ):
                    pass
        self.assertFalse((self.root/"auto-canary.lock").exists())

    def test_timeout_type_and_range_strict(self):
        for value in (-1, 10.1, True, float("nan"), float("inf"), "1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    with self.acquire(timeout=value):
                        pass
        self.assertFalse((self.root/"auto-canary.lock").exists())

    def test_pending_journal_fails_under_lock(self):
        (self.root / "rag-del-x.journal.json").write_text(
            "{}",encoding="utf-8",
        )
        with self.assertRaisesRegex(LaboratoryCatalogUnsafe, "journal"):
            with self.acquire():
                pass
        (self.root / "rag-del-x.journal.json").unlink()
        with self.acquire():
            pass

    def test_missing_catalog_rejected_without_creating_lock(self):
        self.catalog.unlink()
        with self.assertRaises(LaboratoryCatalogUnsafe):
            with self.acquire():
                pass
        self.assertFalse((self.root/"auto-canary.lock").exists())

    def test_catalog_outside_temp_root_refused(self):
        not_scratch = self.root / "not-a-scratch-subfolder"
        not_scratch.mkdir()
        other = not_scratch / "project-indexes.json"
        other.write_text("{}",encoding="utf-8")
        with self.assertRaises((LaboratoryCatalogUnsafe, RuntimeError, ValueError)):
            with bounded_catalog_mutex_lab(
                other, laboratory_mode=True, operator_approved=True,
            ):
                pass
        self.assertFalse((not_scratch/"auto-canary.lock").exists())

    def test_redirected_lock_refused_when_symlinks_available(self):
        outer = self.root / "external.txt"
        outer.write_bytes(b"UNTOUCHED")
        lock = self.root / "auto-canary.lock"
        try:
            lock.symlink_to(outer)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("Windows symlink permission unavailable: "+str(exc))
        with self.assertRaises(LaboratoryCatalogUnsafe):
            with self.acquire():
                pass
        self.assertEqual(outer.read_bytes(), b"UNTOUCHED")

    def test_killed_writer_releases_lock_and_reader_recovers(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", _CHILD, str(self.root)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        try:
            self.assertEqual(proc.stdout.readline().strip(), "HELD")
            with self.assertRaises(LaboratoryCatalogBusy):
                with self.acquire(timeout=0.03):
                    pass
        finally:
            proc.kill()
            proc.communicate(timeout=5)
        with self.acquire(timeout=0.3):
            pass
        self.assertNotEqual(proc.returncode, 0)
