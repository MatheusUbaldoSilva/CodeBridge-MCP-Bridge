"""The production backup preflight is read-only and does not grant permission."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.production_backup_preflight import inspect_backup_prerequisites


class BackupPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "closed"
        create_bundle(self.root, [("a", "manual", "original")])
        self.db = self.root / "rag_index.sqlite3"
        self.manifest = self.root / "rag-index-manifest.json"
        self.qdrant = self.root / "qdrant"

    def inspect(self, quiet=False):
        return inspect_backup_prerequisites(
            self.db, self.manifest, self.qdrant,
            operator_asserted_quiesced=quiet)

    def test_live_app_blocks_snapshot_despite_healthy_stores(self):
        report = self.inspect()
        self.assertEqual(report["state"], "BLOCKED")
        self.assertIn("APPLICATION_QUIESCENCE_NOT_CONFIRMED", report["issues"])
        self.assertEqual((report["documents"], report["chunks"], report["manifest_entries"]),
                         (1, 1, 1))
        self.assertFalse(report["copy_authorized"])
        self.assertFalse(report["publication_authorized"])

    def test_quiet_fixture_is_only_a_candidate_not_permission(self):
        before = [hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in (self.db, self.manifest)]
        report = self.inspect(quiet=True)
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["state"], "OFFLINE_CANDIDATE_REQUIRES_VERIFIED_SNAPSHOT")
        self.assertTrue(report["read_only"])
        self.assertFalse(report["copy_authorized"])
        self.assertEqual(before, [hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in (self.db, self.manifest)])

    def test_rejects_wal_sidecar_even_with_quiescence_asserted(self):
        sidecar = self.db.with_name(self.db.name + "-wal")
        sidecar.write_bytes(b"present")
        report = self.inspect(quiet=True)
        self.assertEqual(report["state"], "BLOCKED")
        self.assertIn("SQLITE_SIDECAR_PRESENT", report["issues"])

    def test_rejects_manifest_mismatch(self):
        from rag.index.manifest import IndexManifest, save_index_manifest
        save_index_manifest(self.manifest, IndexManifest(()))
        report = self.inspect(quiet=True)
        self.assertIn("MANIFEST_SQLITE_MISMATCH", report["issues"])
        self.assertEqual(report["state"], "BLOCKED")

    def test_missing_qdrant_is_blocked(self):
        report = inspect_backup_prerequisites(self.db, self.manifest,
                                             self.root / "nonexistent",
                                             operator_asserted_quiesced=True)
        self.assertIn("QDRANT_MISSING", report["issues"])
        self.assertFalse(report["copy_authorized"])


    def test_empty_qdrant_is_blocked(self):
        empty = self.root / "empty-qdrant"
        empty.mkdir()
        result = inspect_backup_prerequisites(
            self.db, self.manifest, empty, operator_asserted_quiesced=True)
        self.assertIn("QDRANT_EMPTY", result["issues"])

    def test_sqlite_wal_sidecar_does_not_open_live_database(self):
        self.db.with_name(self.db.name + "-wal").write_bytes(b"pending")
        with patch("rag.runtime.production_backup_preflight.sqlite3.connect",
                   side_effect=AssertionError("should not open live WAL")):
            result = self.inspect(quiet=True)
        self.assertIn("SQLITE_SIDECAR_PRESENT", result["issues"])
        self.assertFalse(result["copy_authorized"])


if __name__ == "__main__":
    unittest.main()
