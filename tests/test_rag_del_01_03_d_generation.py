"""RAG_DEL_01 resolver verifier temporary fixtures."""
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from rag.runtime.knowledge_deletion_generation import (
    DeletionGenerationUnavailable, verify_deletion_generation,digest_file,
)
from rag.runtime.knowledge_deletion_qdrant_freeze import fingerprint_closed_qdrant_store

class DeletionGenerationVerifierTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root=Path(tmp.name)
        tid="a"*32
        self.generation=root/"generations"/("del_"+tid)
        self.generation.mkdir(parents=True)
        self.source=root/"snapshots"/("source_"+tid)
        self.source.mkdir(parents=True)
        self.revision="b"*64
        self.row={"index_family":"RAG_DEL_01","transaction_id":tid,
                  "generation_receipt_sha256":None}
        (self.generation/"rag_index.sqlite3").write_bytes(b"sqlite")
        (self.generation/"rag-index-manifest.json").write_bytes(b"manifest")
        (self.generation/"qdrant").mkdir()
        (self.generation/"qdrant"/"segment.bin").write_bytes(b"fake-vector")
        qdrant_hash=fingerprint_closed_qdrant_store(self.generation/"qdrant")["inventory_sha256"]
        self.row["sqlite_sha256"]=digest_file(self.generation/"rag_index.sqlite3")
        self.row["manifest_sha256"]=digest_file(self.generation/"rag-index-manifest.json")
        self.receipt={
            "schema_version":1,"state":"VERIFIED_NOT_REGISTERED",
            "index_family":"RAG_DEL_01","transaction_id":tid,"project_id":"demo",
            "source_revision":self.revision,"source_snapshot":str(self.source),
            "published_publicly":False,"activation_authorized":False,
            "baseline_generation":"auto_old","selection_sha256":"c"*64,
            "review_bundle_sha256":"d"*64,
            "sqlite_sha256":self.row["sqlite_sha256"],
            "manifest_sha256":self.row["manifest_sha256"],
            "qdrant_inventory_sha256":qdrant_hash,"vectors_verified":2,
        }
        self.progress={"project_id":"demo","source_revision":self.revision,
            "transaction_id":tid,"state":"INDEXING_NOT_PUBLISHED",
            "last_batch_result":"COMPLETE","total_vectors_done":2,
            "expected_chunks":2,"published":False}
        self.persist()
    def persist(self):
        r=self.generation/"deletion-generation-receipt.json"
        r.write_text(json.dumps(self.receipt),encoding="utf-8")
        self.row["generation_receipt_sha256"]=digest_file(r)
        (self.generation/"progress.json").write_text(json.dumps(self.progress),encoding="utf-8")
    def verify(self):
        return verify_deletion_generation(self.row,"demo",self.generation,self.source,self.revision)
    def test_fully_pinned_fixture(self):
        self.assertEqual(self.verify()["project_id"],"demo")
    def test_tampered_receipt_digest(self):
        self.row["generation_receipt_sha256"]="0"*64
        with self.assertRaises(DeletionGenerationUnavailable): self.verify()
    def test_wrong_receipt_project(self):
        self.receipt["project_id"]="other"
        self.persist()
        with self.assertRaises(DeletionGenerationUnavailable): self.verify()
    def test_modified_qdrant_store(self):
        (self.generation/"qdrant"/"segment.bin").write_bytes(b"tampered")
        with self.assertRaises(DeletionGenerationUnavailable): self.verify()
    def test_modified_sqlite(self):
        (self.generation/"rag_index.sqlite3").write_bytes(b"changed")
        with self.assertRaises(DeletionGenerationUnavailable): self.verify()
    def test_progress_mismatch(self):
        self.progress["total_vectors_done"]=1
        self.persist()
        with self.assertRaises(DeletionGenerationUnavailable): self.verify()
    def test_wrong_family(self):
        self.receipt["index_family"]="RAG_AUTO_03"
        self.persist()
        with self.assertRaises(DeletionGenerationUnavailable): self.verify()
    def test_wrong_generation_directory(self):
        with self.assertRaises(DeletionGenerationUnavailable):
            verify_deletion_generation(self.row,"demo",self.source,self.source,self.revision)
