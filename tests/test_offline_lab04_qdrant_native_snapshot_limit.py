"""Qdrant Local native snapshot API boundaries in disposable lab only."""
import importlib.metadata
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qdrant_client import QdrantClient

class QdrantLocalNativeSnapshotLimits(unittest.TestCase):
    def test_native_snapshot_apis_are_unavailable_in_installed_local_backend(self):
        with tempfile.TemporaryDirectory(prefix="codebridge-qdrant-local-api-") as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            client = QdrantClient(path=str(root / "qdrant"))
            try:
                with self.assertRaisesRegex(NotImplementedError, "local Qdrant"):
                    client.create_full_snapshot()
                with self.assertRaisesRegex(NotImplementedError, "local Qdrant"):
                    client.create_snapshot(collection_name="text")
                with self.assertRaisesRegex(NotImplementedError, "local Qdrant"):
                    client.recover_snapshot(collection_name="text", location="file:///synthetic.snapshot")
                self.assertEqual(client.list_snapshots(collection_name="text"), [])
            finally:
                client.close()

if __name__ == "__main__":
    unittest.main()
