"""Resolver integration for a fully pinned RAG_DEL_01 temporary generation."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import sys
from rag.runtime.isolated_project_index import resolve_isolated_project,IsolatedProjectUnavailable
from rag.runtime.knowledge_deletion_generation import digest_file
from rag.runtime.knowledge_deletion_qdrant_freeze import fingerprint_closed_qdrant_store

class ResolverDeletionFamilyTests(TestCase):
    def setUp(self):
        t=TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.workspace=Path(t.name)
        self.tid="d"*32
        self.gen=self.workspace/"generations"/("del_"+self.tid)
        self.gen.mkdir(parents=True)
        self.source=self.workspace/"snapshots"/("source_"+self.tid)
        self.source.mkdir(parents=True)
        self.rev="e"*64
        (self.gen/"rag_index.sqlite3").write_bytes(b"db")
        (self.gen/"rag-index-manifest.json").write_bytes(b"manifest")
        (self.gen/"qdrant").mkdir()
        (self.gen/"qdrant"/"vectors.bin").write_bytes(b"vectors")
        sha_db=digest_file(self.gen/"rag_index.sqlite3")
        sha_manifest=digest_file(self.gen/"rag-index-manifest.json")
        self.receipt={"schema_version":1,"state":"VERIFIED_NOT_REGISTERED",
              "index_family":"RAG_DEL_01","transaction_id":self.tid,
              "project_id":"demo","source_revision":self.rev,
              "source_snapshot":str(self.source),"published_publicly":False,
              "activation_authorized":False,"baseline_generation":"auto_old",
              "selection_sha256":"a"*64,"review_bundle_sha256":"b"*64,
              "sqlite_sha256":sha_db,"manifest_sha256":sha_manifest,
              "qdrant_inventory_sha256":fingerprint_closed_qdrant_store(self.gen/"qdrant")["inventory_sha256"],
              "vectors_verified":1}
        self.progress={"project_id":"demo","transaction_id":self.tid,
              "source_revision":self.rev,"state":"INDEXING_NOT_PUBLISHED",
              "total_vectors_done":1,"expected_chunks":1,
              "last_batch_result":"COMPLETE","published":False}
        (self.gen/"progress.json").write_text(json.dumps(self.progress))
        self.row={"enabled":True,"project_id":"demo","index_family":"RAG_DEL_01",
                  "transaction_id":self.tid,"source_revision":self.rev,
                  "generation_directory":str(self.gen),
                  "source_directory":str(self.source),
                  "python_executable":sys.executable,
                  "sqlite_sha256":sha_db,"manifest_sha256":sha_manifest}
        self.persist()
        for name,value in (("rag.runtime.isolated_project_index._entries",{"demo":self.row}),
                          ("rag.runtime.isolated_project_index._workspace_root",self.workspace)):
            p=patch(name,return_value=value)
            p.start()
            self.addCleanup(p.stop)
    def persist(self):
        r=self.gen/"deletion-generation-receipt.json"
        r.write_text(json.dumps(self.receipt))
        self.row["generation_receipt_sha256"]=digest_file(r)
    def test_resolver_loads_valid_private_generation(self):
        result=resolve_isolated_project("demo")
        self.assertEqual(result.generation,"del_"+self.tid)
        self.assertEqual(result.source_revision,self.rev)
    def test_changed_qdrant_rejected(self):
        (self.gen/"qdrant"/"vectors.bin").write_bytes(b"tampered")
        with self.assertRaises(IsolatedProjectUnavailable): resolve_isolated_project("demo")
    def test_changed_receipt_rejected(self):
        self.receipt["selection_sha256"]="c"*64
        (self.gen/"deletion-generation-receipt.json").write_text(json.dumps(self.receipt))
        with self.assertRaises(IsolatedProjectUnavailable): resolve_isolated_project("demo")
    def test_progress_out_of_sync_rejected(self):
        self.progress["expected_chunks"]=2
        (self.gen/"progress.json").write_text(json.dumps(self.progress))
        with self.assertRaises(IsolatedProjectUnavailable): resolve_isolated_project("demo")
    def test_unknown_family_rejected(self):
        self.row["index_family"]="UNKNOWN"
        with self.assertRaises(IsolatedProjectUnavailable): resolve_isolated_project("demo")
