"""Read-only candidate structure validator tests: temporary SQLite only."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch,Mock
import sqlite3

from rag.index.sqlite_schema import connect_rag_index
from rag.index.fts5 import initialize_fts5
from rag.index.manifest import IndexManifest,ManifestEntry,ManifestIndexKind,save_index_manifest
from rag.runtime.auto_index_incremental_checkpoint import persist_isolated_batch_receipt
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError
from rag.runtime.knowledge_deletion_verify import validate_deletion_candidate


class DeletionCandidateValidationTests(TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.stage=Path(temp.name)/"candidate"
        self.stage.mkdir()
        self.db=self.stage/"rag_index.sqlite3"
        self.manifest=self.stage/"rag-index-manifest.json"
        with closing(connect_rag_index(self.db)) as cn:
            cn.execute("INSERT INTO rag_documents(document_id,project_id,source_type,content,path,sha256) VALUES(?,?,?,?,?,?)",
                       ("docb","demo","CODE","content","b.cpp","a"*64))
            cn.execute("INSERT INTO rag_chunks(chunk_id,document_id,project_id,ordinal,content,source_type,path) VALUES(?,?,?,?,?,?,?)",
                       ("cb","docb","demo",0,"content","CODE","b.cpp"))
            cn.commit()
            initialize_fts5(cn,rebuild=True)
            cn.commit()
        save_index_manifest(self.manifest,IndexManifest((ManifestEntry(
            project_id="demo",index_kind=ManifestIndexKind.CODE,path="b.cpp",
            size=1,mtime_ns=1,sha256="a"*64,chunk_ids=("cb",),
            model_version="test"),)))
        self.bid="c"*32
        persist_isolated_batch_receipt(self.stage,self.bid,{
            "mode":"ISOLATED_STAGE_BATCH_WRITTEN",
            "vectors_written":1,"public_pointer_updated":False,
            "requires_staging_revalidation":True},allow_write=True)
        self.plan={"state":"SURVIVOR_RECEIPTS_ONLY","project_id":"demo",
                   "vectors_to_preserve":1,"batches":[{"candidate_vector_count":1}],
                   "sources":{"sources":[{"path":"b.cpp","sha256":"a"*64,"index_kind":"CODE"}]}}
        p=patch("rag.runtime.knowledge_deletion_verify.read_reusable_vectors",
                return_value={"TEXT":[],"CODE":[{"id":"c"}]})
        self.reader=p.start()
        self.addCleanup(p.stop)

    def verify(self):
        return validate_deletion_candidate(self.stage,self.plan,Mock(),[self.bid])

    def test_candidate_valid_but_not_activated(self):
        result=self.verify()
        self.assertEqual(result["vectors_verified"],1)
        self.assertEqual(result["state"],"DELETION_STAGING_STRUCTURALLY_VALID")
        self.assertFalse(result["activation_authorized"])

    def test_tampered_sha_refused(self):
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("UPDATE rag_documents SET sha256=?",("b"*64,))
            cn.commit()
        with self.assertRaises(IncrementalPlanError):
            self.verify()

    def test_missing_checkpoint_refused(self):
        (self.stage/("batch_"+self.bid+".json")).unlink()
        with self.assertRaises(IncrementalPlanError):
            self.verify()

    def test_wrong_batch_count_refused(self):
        self.plan["vectors_to_preserve"]=2
        with self.assertRaises(IncrementalPlanError):
            self.verify()

    def test_foreign_project_refused(self):
        self.plan["project_id"]="codebridge"
        with self.assertRaises(IncrementalPlanError):
            self.verify()
