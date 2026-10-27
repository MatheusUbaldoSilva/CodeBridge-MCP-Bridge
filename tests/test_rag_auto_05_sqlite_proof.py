"""RAG-AUTO-05-F pre-write candidate SQLite matching tests."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from rag.runtime.auto_index_incremental_sqlite import verify_candidate_stage_rows
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


class CandidateRowProofTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db=Path(tmp.name)/"candidate.sqlite3"
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute(
                "CREATE TABLE rag_chunks(chunk_id TEXT, document_id TEXT, "
                "project_id TEXT,content TEXT,source_type TEXT,path TEXT,sha256 TEXT)"
            )
            cn.execute(
                "INSERT INTO rag_chunks VALUES(?,?,?,?,?,?,?)",
                ("chunk-1","doc-1","lab-project","content v1","CODE",
                 "main.py","a"*64),
            )
            cn.commit()
        self.records={"TEXT":[],"CODE":[{
            "payload":{"chunk_id":"chunk-1","document_id":"doc-1",
                "project_namespace":"lab-project","content":"content v1",
                "source_type":"CODE","path":"main.py","sha256":"a"*64},
        }]}

    def test_exact_payload_passes(self):
        self.assertEqual(verify_candidate_stage_rows(
            self.db,"lab-project",self.records)["matched_rows"],1)

    def test_mutated_payload_rejected(self):
        for key,value in (
            ("content","changed"),("document_id","other"),
            ("project_namespace","other"),("sha256","b"*64),
            ("path","other.py"),("source_type","DOCUMENTATION"),
        ):
            with self.subTest(field=key):
                record=self.records["CODE"][0]["payload"]
                previous=record[key]
                record[key]=value
                try:
                    with self.assertRaises(IncrementalPlanError):
                        verify_candidate_stage_rows(self.db,"lab-project",self.records)
                finally:
                    record[key]=previous

    def test_missing_chunk_rejected(self):
        self.records["CODE"][0]["payload"]["chunk_id"]="unknown"
        with self.assertRaises(IncrementalPlanError):
            verify_candidate_stage_rows(self.db,"lab-project",self.records)

    def test_empty_batch_rejected(self):
        with self.assertRaises(IncrementalPlanError):
            verify_candidate_stage_rows(
                self.db,"lab-project",{"TEXT":[],"CODE":[]})
