import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot
from rag.runtime.offline_restore_equivalence import audit_restored_fixture
import rag.runtime.offline_restore_equivalence as audit

class RestoreEquivalenceQdrantSidecarTests(unittest.TestCase):
    def test_matching_internal_qdrant_sidecars_still_block_equivalence(self):
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix):
                with tempfile.TemporaryDirectory(prefix="rag-lab04-equivalence-") as tmp:
                    root = Path(tmp) / "codebridge-rag-generation-test"
                    create_bundle(root, [("lab", "same-sidecar", "synthetic")])
                    capture_fixture(root, "saved")
                    restore_fixture_snapshot(root, "saved", "restored")
                    backup = root / "offline-fixture-backups" / "saved"
                    original = backup / "snapshot"
                    restored = root / "offline-fixture-restores" / "restored" / "snapshot"
                    sqlite = next((original / "qdrant").rglob("storage.sqlite"))
                    relative = sqlite.relative_to(original)
                    for directory in (original, restored):
                        Path(str(directory / relative) + suffix).write_bytes(b"synthetic-sidecar")
                    metadata = backup / "report.json"
                    report = json.loads(metadata.read_text(encoding="utf-8"))
                    report["hashes"] = audit._hash_tree(original)
                    metadata.write_text(json.dumps(report), encoding="utf-8")
                    # Isolate the sidecar gate even when a semantic validator accepts data.
                    with patch.object(audit, "validate_incremental_bundle", return_value=report["verification"]):
                        result = audit_restored_fixture(root, "saved", "restored")
                    self.assertEqual(result["state"], "BLOCKED")
                    self.assertFalse(result["same_hashes"])
                    self.assertFalse(result["production_authorized"])
                    self.assertFalse(result["publication_authorized"])

if __name__ == "__main__":
    unittest.main()
