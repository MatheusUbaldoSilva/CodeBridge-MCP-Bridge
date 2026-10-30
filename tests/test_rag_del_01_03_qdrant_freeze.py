from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from rag.runtime.knowledge_deletion_qdrant_freeze import (
    QdrantFreezeError, fingerprint_closed_qdrant_store, verify_closed_qdrant_inventory
)

class ClosedStoreFreezeTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder=Path(tmp.name)/"qdrant"
        self.folder.mkdir()
        (self.folder/"storage.bin").write_bytes(b"one")
        (self.folder/"other.json").write_bytes(b"two")

    def test_deterministic_and_read_only(self):
        before=(self.folder/"storage.bin").read_bytes()
        result=fingerprint_closed_qdrant_store(self.folder)
        second=fingerprint_closed_qdrant_store(self.folder)
        self.assertEqual(result,second)
        self.assertEqual(result["total_files"],2)
        self.assertEqual(result["total_bytes"],6)
        self.assertFalse(result["activation_authorized"])
        self.assertEqual((self.folder/"storage.bin").read_bytes(),before)

    def test_change_detectable(self):
        first=fingerprint_closed_qdrant_store(self.folder)
        (self.folder/"storage.bin").write_bytes(b"changed")
        second=fingerprint_closed_qdrant_store(self.folder)
        self.assertNotEqual(first["inventory_sha256"],second["inventory_sha256"])

    def test_revalidate_saved_inventory(self):
        saved=fingerprint_closed_qdrant_store(self.folder)
        checked=verify_closed_qdrant_inventory(self.folder,saved)
        self.assertEqual(checked["inventory_sha256"],saved["inventory_sha256"])
        (self.folder/"other.json").write_text("changed")
        with self.assertRaises(QdrantFreezeError):
            verify_closed_qdrant_inventory(self.folder,saved)

    def test_empty_folder_rejected(self):
        (self.folder/"storage.bin").unlink()
        (self.folder/"other.json").unlink()
        with self.assertRaises(QdrantFreezeError):
            fingerprint_closed_qdrant_store(self.folder)

    def test_limit_exceeded_rejected(self):
        with self.assertRaises(QdrantFreezeError):
            fingerprint_closed_qdrant_store(self.folder,max_files=1)
        with self.assertRaises(QdrantFreezeError):
            fingerprint_closed_qdrant_store(self.folder,max_bytes=2)

    def test_real_closed_qdrant_local_store(self):
        from rag.index.qdrant_local import open_qdrant_local, close_qdrant_local, ensure_vector_collections
        root=self.folder.parent/"realstore"
        client=open_qdrant_local(root)
        try:
            ensure_vector_collections(client)
        finally:
            close_qdrant_local(client)
        first=fingerprint_closed_qdrant_store(root)
        self.assertGreater(first["total_files"],0)
        second=fingerprint_closed_qdrant_store(root)
        self.assertEqual(first["inventory_sha256"],second["inventory_sha256"])

    def test_redirected_file_rejected_when_available(self):
        outside=self.folder.parent/"outside.txt"
        outside.write_text("outside")
        try:
            (self.folder/"redirect.txt").symlink_to(outside)
        except OSError:
            self.skipTest("Windows symlinks unavailable")
        with self.assertRaises(QdrantFreezeError):
            fingerprint_closed_qdrant_store(self.folder)
