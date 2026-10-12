"""Backup reconstruction in an isolated test generation; never activates it."""
import hashlib
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_verified_backup import backup_generation
from rag.runtime.generation_backup_restore_copy import (
    restore_verified_backup_as_test_copy, BackupRestoreCopyError)
from rag.runtime.incremental_bundle_validate import validate_incremental_bundle


class IsolatedBackupCopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "codebridge-rag-generation-test"
        (self.root / "generations").mkdir(parents=True)
        self.original = self.root / "generations" / "one"
        create_bundle(self.original, [
            ("a", "document", "original"),
            ("b", "other", "preserved")])
        activate_test_generation(self.root, "one")
        backup_generation(self.root, "one", "saved")

    def restore(self, name="restored", **kwargs):
        return restore_verified_backup_as_test_copy(
            self.root, "saved", name, **kwargs)

    def test_full_cross_store_restore_without_activation(self):
        pointer = (self.root / "active-generation.json").read_bytes()
        before = hashlib.sha256(
            (self.original / "rag_index.sqlite3").read_bytes()).hexdigest()
        report = self.restore()
        self.assertEqual(report["state"], "TEST_RESTORED_COPY_NOT_ACTIVATED")
        self.assertEqual(report["active_generation"], "one")
        self.assertEqual(report["report"]["documents"], 2)
        self.assertEqual(report["report"]["chunks"], 2)
        self.assertEqual(report["report"]["vectors"], 2)
        self.assertEqual(validate_incremental_bundle(
            self.root / "generations" / "restored")["manifest_entries"], 2)
        self.assertEqual(resolve_generation(self.root).generation, "one")
        self.assertEqual((self.root / "active-generation.json").read_bytes(), pointer)
        self.assertEqual(hashlib.sha256(
            (self.original / "rag_index.sqlite3").read_bytes()).hexdigest(), before)
        self.assertFalse(list((self.root / "generations").glob(".restore-copy-*")))

    def test_corrupted_backup_is_rejected_without_target(self):
        (self.root / "backups" / "saved" / "rag-index-manifest.json").write_text(
            "corrupted", encoding="utf-8")
        with self.assertRaisesRegex(BackupRestoreCopyError, "verification failed"):
            self.restore()
        self.assertFalse((self.root / "generations" / "restored").exists())
        self.assertEqual(resolve_generation(self.root).generation, "one")

    def test_existing_target_is_never_overwritten(self):
        prior = (self.original / "rag_index.sqlite3").read_bytes()
        with self.assertRaisesRegex(BackupRestoreCopyError, "overwrite refused"):
            self.restore("one")
        self.assertEqual((self.original / "rag_index.sqlite3").read_bytes(), prior)
        self.assertEqual(resolve_generation(self.root).generation, "one")

    def test_injected_failure_cleans_staging_only(self):
        with self.assertRaisesRegex(BackupRestoreCopyError, "injected failure"):
            self.restore(fail_after_copy=True)
        self.assertFalse((self.root / "generations" / "restored").exists())
        self.assertFalse(list((self.root / "generations").glob(".restore-copy-*")))
        self.assertTrue((self.root / "backups" / "saved").is_dir())
        self.assertEqual(resolve_generation(self.root).generation, "one")

    def test_pending_transition_blocks_copy(self):
        (self.root / "transition-pending.json").write_text(
            '{"schema_version":1,"previous":"one","candidate":"other"}',
            encoding="utf-8")
        with self.assertRaisesRegex(BackupRestoreCopyError, "unresolved transition"):
            self.restore()
        self.assertFalse((self.root / "generations" / "restored").exists())

    def test_non_test_root_and_invalid_names_rejected(self):
        child = self.root / "production-like"
        child.mkdir()
        with self.assertRaisesRegex(BackupRestoreCopyError, "isolated test"):
            restore_verified_backup_as_test_copy(child, "saved", "restored")
        for bad in ("../oops", "", "a" * 65):
            with self.subTest(name=bad):
                with self.assertRaisesRegex(BackupRestoreCopyError, "invalid"):
                    self.restore(bad)
        self.assertFalse((self.root / "generations" / "restored").exists())


    def test_concurrent_restore_same_name_only_one_succeeds(self):
        def attempt(_):
            try:
                return self.restore()["state"]
            except (BackupRestoreCopyError, RuntimeError):
                return "REJECTED"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertCountEqual(
            results, ["TEST_RESTORED_COPY_NOT_ACTIVATED", "REJECTED"])
        self.assertEqual(resolve_generation(self.root).generation, "one")
        self.assertEqual(validate_incremental_bundle(
            self.root / "generations" / "restored")["documents"], 2)

    def test_symlinked_backup_parent_and_target_fail_closed(self):
        forbidden = [
            self.root / "backups",
            self.root / "backups" / "saved",
            self.root / "backups" / "saved.sha256.json",
            self.root / "generations",
            self.root / "generations" / "restored",
        ]
        original = Path.is_symlink
        for path in forbidden:
            with self.subTest(path=str(path)):
                with patch.object(
                    Path, "is_symlink",
                    autospec=True,
                    side_effect=lambda candidate, forbidden=path:
                        candidate == forbidden or original(candidate)
                ):
                    with self.assertRaisesRegex(BackupRestoreCopyError, "symlinks"):
                        self.restore()
                self.assertFalse(
                    (self.root / "generations" / "restored").exists())

if __name__ == "__main__":
    unittest.main()
