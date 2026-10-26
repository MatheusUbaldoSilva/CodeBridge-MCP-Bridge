"""RAG-AUTO-02.2 isolated staging preparation tests; no model inference."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime.auto_index_queue import create_draft,default_queue_path
from rag.runtime.auto_index_approval import build_auto_index_preview,approve_auto_index_draft
from rag.runtime.auto_index_staging import prepare_auto_staging,stage_directory


class AutoStagingTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name)
        self.project="auto-stage-test"
        self.root=self.base/"sample-source"
        self.root.mkdir()
        (self.root/"README.md").write_bytes(b"Project knowledge\r\nInstall instructions\r\n")
        (self.root/"module.py").write_text("def useful():\n    return 37\n",encoding="utf-8")
        self.db=default_queue_path(self.base)
        job=create_draft(
            self.db,project_id=self.project,source_root=self.root,
            idempotency_key="test-stage-123456789",allow_write=True,
        )
        self.job_id=job["job_id"]
        preview=build_auto_index_preview(self.project,self.root)
        approve_auto_index_draft(
            self.db,self.job_id,preview,confirmed_digest=preview["review_sha256"],
            operator_approved=True,allow_write=True,
        )

    def prepare(self):
        return prepare_auto_staging(
            self.db,self.job_id,operator_approved=True,preparation_enabled=True,
        )

    def test_not_prepared_until_explicit_authorization(self):
        with self.assertRaises(PermissionError):
            prepare_auto_staging(self.db,self.job_id)
        self.assertFalse(stage_directory(self.db,self.job_id).exists())

    def test_generates_rag_db_fts_qdrant_and_manifest(self):
        stage=self.prepare()
        self.assertEqual(stage["documents"],2)
        self.assertGreater(stage["chunks"],0)
        self.assertEqual(stage["text_chunks"]+stage["code_chunks"],stage["chunks"])
        self.assertFalse(stage["worker_started"])
        self.assertFalse(stage["index_published"])
        root=Path(stage["stage"])
        for file in ("rag_index.sqlite3","rag-index-manifest.json","progress.json"):
            self.assertTrue((root/file).is_file(),file)
        self.assertTrue((root/"qdrant").is_dir())
        with closing(sqlite3.connect(f"{(root/'rag_index.sqlite3').as_uri()}?mode=ro",uri=True)) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0],"ok")
            self.assertEqual(conn.execute("SELECT count(*) FROM rag_documents").fetchone()[0],2)
            self.assertEqual(conn.execute("SELECT count(*) FROM rag_chunks_fts").fetchone()[0],stage["chunks"])
        progress=json.loads((root/"progress.json").read_text(encoding="utf-8"))
        self.assertEqual(progress["expected_chunks"],stage["chunks"])
        self.assertEqual(progress["total_vectors_done"],0)
        self.assertFalse(progress["published"])

    def test_existing_complete_stage_is_reused(self):
        first=self.prepare()
        second=self.prepare()
        self.assertTrue(second["reused"])
        self.assertEqual(first["stage"],second["stage"])

    def test_mutated_source_after_review_refused(self):
        (self.root/"module.py").write_text("print('changed')\n",encoding="utf-8")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(stage_directory(self.db,self.job_id).exists())

    def test_model_writing_not_called_by_staging(self):
        with patch("rag.runtime.production_index._write_vectors",
                   side_effect=AssertionError("no model load allowed")):
            self.prepare()

    def test_corrupted_existing_stage_refused(self):
        stage=Path(self.prepare()["stage"])
        (stage/"progress.json").write_text('{"published":true}',encoding="utf-8")
        with self.assertRaises(Exception):
            self.prepare()

    def test_redirected_existing_stage_refused(self):
        from rag.runtime.auto_index_queue import AutoIndexQueueError
        target=self.base/"not-an-index"
        target.mkdir()
        stage=stage_directory(self.db,self.job_id)
        stage.parent.mkdir(parents=True,exist_ok=True)
        try:
            stage.symlink_to(target,target_is_directory=True)
        except OSError as exc:
            if getattr(exc,"winerror",None)==1314:
                self.skipTest("Windows account lacks symlink privilege")
            raise
        with self.assertRaises(AutoIndexQueueError):
            self.prepare()
        self.assertFalse((target/"rag_index.sqlite3").exists())


if __name__=="__main__":
    unittest.main()
