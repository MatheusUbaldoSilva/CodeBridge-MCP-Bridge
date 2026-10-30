from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from rag.index.manifest import IndexManifest,ManifestEntry,ManifestIndexKind,save_index_manifest
from rag.runtime.knowledge_deletion_snapshot import inspect_survivor_snapshot,DeletionSnapshotError

class SnapshotSurvivorTests(TestCase):
    def setUp(self):
        t=TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.snapshot=self.root/"snapshot"
        (self.snapshot/"game"/"src").mkdir(parents=True)
        self.file=self.snapshot/"game"/"src"/"shop.cpp"
        self.file.write_bytes(b"hello source")
        self.manifest=self.root/"manifest.json"
        self.write_manifest("game/src/shop.cpp",sha256(b"hello source").hexdigest())
    def write_manifest(self,path,hash):
        save_index_manifest(self.manifest,IndexManifest((ManifestEntry(
            project_id="demo",index_kind=ManifestIndexKind.CODE,
            path=path,size=12,mtime_ns=1,sha256=hash,
            chunk_ids=("chunk1",),model_version="lab"),)))
    def inspect(self):
        return inspect_survivor_snapshot(self.snapshot,self.manifest,"demo")
    def test_matches_file_hash(self):
        result=self.inspect()
        self.assertEqual(result["files_verified"],1)
        self.assertFalse(result["activation_authorized"])
    def test_manifest_size_mismatch_rejected(self):
        save_index_manifest(self.manifest,IndexManifest((ManifestEntry(
            project_id="demo",index_kind=ManifestIndexKind.CODE,
            path="game/src/shop.cpp",size=999,mtime_ns=1,
            sha256=sha256(b"hello source").hexdigest(),
            chunk_ids=("chunk1",),model_version="lab"),)))
        with self.assertRaises(DeletionSnapshotError):self.inspect()

    def test_content_change_rejected(self):
        self.file.write_bytes(b"changed")
        with self.assertRaises(DeletionSnapshotError):self.inspect()
    def test_parent_path_rejected_by_manifest(self):
        with self.assertRaises(ValueError):
            self.write_manifest("../secret.cpp","a"*64)
    def test_windows_backslash_rejected(self):
        self.write_manifest(r"game\src\shop.cpp","a"*64)
        with self.assertRaises(DeletionSnapshotError):self.inspect()
    def test_missing_file_rejected(self):
        self.file.unlink()
        with self.assertRaises(DeletionSnapshotError):self.inspect()
    def test_size_limit_rejected(self):
        with self.assertRaises(DeletionSnapshotError):
            inspect_survivor_snapshot(self.snapshot,self.manifest,"demo",max_bytes=2)
    def test_foreign_project_rejected(self):
        with self.assertRaises(DeletionSnapshotError):
            inspect_survivor_snapshot(self.snapshot,self.manifest,"other")
