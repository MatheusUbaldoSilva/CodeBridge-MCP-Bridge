"""RAG-AUTO-01.2 durable multi-project draft queue tests (no models)."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from rag.runtime.auto_index_queue import (
    AutoIndexQueueError, create_draft, default_queue_path,
    get_job, inspect_queue, list_events, list_jobs,
)


class AutoIndexQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)
        self.db=default_queue_path(self.home)
        self.root=self.home/"example-project"
        self.root.mkdir()
        self.args={
            "project_id":"codebrige-mcp-rag",
            "source_root":self.root,
            "idempotency_key":"request-0123456789abcdef",
            "allow_write":True,
            "now_epoch":100.0,
        }

    def test_import_and_reads_do_not_create_store(self):
        self.assertEqual(inspect_queue(self.db)["state"],"NOT_INITIALIZED")
        self.assertEqual(list_jobs(self.db),[])
        self.assertIsNone(get_job(self.db,"a"*32))
        self.assertFalse(self.db.exists())
        self.assertFalse(self.db.parent.exists())

    def test_explicit_write_permission_required(self):
        with self.assertRaises(PermissionError):
            create_draft(self.db,**{**self.args,"allow_write":False})
        self.assertFalse(self.db.exists())

    def test_draft_insert_is_durable_and_inert(self):
        result=create_draft(self.db,**self.args)
        self.assertTrue(result["inserted"])
        self.assertEqual(result["state"],"DRAFT")
        self.assertEqual(result["approved"],False)
        self.assertEqual(result["project_id"],"codebrige-mcp-rag")
        self.assertEqual(result["file_count"],0)
        self.assertEqual(result["chunk_count"],0)
        self.assertEqual(result["text_vectors_done"],0)
        self.assertFalse(result["worker_started"])
        self.assertFalse(result["index_updated"])
        self.assertFalse(result["publication_authorized"])
        self.assertEqual(get_job(self.db,result["job_id"])["job_id"],result["job_id"])
        self.assertEqual(inspect_queue(self.db)["integrity"],"ok")
        self.assertEqual(list_events(self.db,result["job_id"])[0]["event_type"],"DRAFT_CREATED")

    def test_repeated_request_is_idempotent(self):
        a=create_draft(self.db,**self.args)
        b=create_draft(self.db,**self.args)
        self.assertEqual(a["job_id"],b["job_id"])
        self.assertFalse(b["inserted"])
        self.assertEqual(inspect_queue(self.db)["jobs"],1)
        self.assertEqual(len(list_events(self.db,a["job_id"])),1)

    def test_key_reuse_with_conflicting_project_is_forbidden(self):
        create_draft(self.db,**self.args)
        with self.assertRaises(AutoIndexQueueError):
            create_draft(self.db,**{**self.args,"project_id":"another-project"})
        self.assertEqual(inspect_queue(self.db)["jobs"],1)

    def test_reopen_new_connection_keeps_draft(self):
        item=create_draft(self.db,**self.args)
        self.assertEqual(list_jobs(self.db)[0]["job_id"],item["job_id"])
        self.assertEqual(list_jobs(self.db)[0]["state"],"DRAFT")
        self.assertEqual(inspect_queue(self.db)["by_state"],{"DRAFT":1})

    def test_multiple_projects_are_separate(self):
        create_draft(self.db,**self.args)
        create_draft(self.db,**{**self.args,"project_id":"newworldpvp",
                                "idempotency_key":"newworld-0123456789abc"})
        self.assertEqual(len(list_jobs(self.db)),2)
        self.assertEqual(len(list_jobs(self.db,project_id="newworldpvp")),1)
        self.assertEqual(len(list_jobs(self.db,project_id="codebrige-mcp-rag")),1)

    def test_concurrent_duplicate_requests_create_one_job(self):
        def request(_):
            return create_draft(self.db,**self.args)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(request,range(8)))
        self.assertEqual(len({entry["job_id"] for entry in results}),1)
        self.assertEqual(sum(entry["inserted"] for entry in results),1)
        self.assertEqual(inspect_queue(self.db)["jobs"],1)

    def test_invalid_identifiers_fail_without_writes(self):
        for project in ("../bad","CODEBRIDGE","", "x"):
            with self.subTest(project=project),self.assertRaises(ValueError):
                create_draft(self.db,**{**self.args,"project_id":project})
        with self.assertRaises(ValueError):
            create_draft(self.db,**{**self.args,"idempotency_key":"abc"})
        with self.assertRaises(ValueError):
            create_draft(self.db,**{**self.args,"scope":"DANGEROUS"})
        self.assertFalse(self.db.exists())

    def test_invalid_root_rejected(self):
        with self.assertRaises(ValueError):
            create_draft(self.db,**{**self.args,"source_root":"relative"})
        with self.assertRaises(FileNotFoundError):
            create_draft(self.db,**{**self.args,"source_root":self.home/"missing"})
        self.assertFalse(self.db.exists())

    def test_unapproved_storage_location_rejected(self):
        bad=self.home/"production"/"rag_index.sqlite3"
        with self.assertRaises(ValueError):
            inspect_queue(bad)
        with self.assertRaises(ValueError):
            create_draft(bad,**self.args)
        self.assertFalse(bad.exists())

    def test_symlink_queue_refused(self):
        real=self.home/"real"
        real.mkdir()
        self.db.parent.parent.mkdir(parents=True,exist_ok=True)
        try:
            self.db.parent.symlink_to(real,target_is_directory=True)
        except OSError as exc:
            if getattr(exc,"winerror",None)==1314:
                self.skipTest("Windows account cannot create symlinks")
            raise
        with self.assertRaises(AutoIndexQueueError):
            create_draft(self.db,**self.args)

    def test_schema_version_drift_fails_closed(self):
        create_draft(self.db,**self.args)
        with closing(sqlite3.connect(self.db)) as con:
            con.execute("PRAGMA user_version=99")
        with self.assertRaises(AutoIndexQueueError):
            list_jobs(self.db)
        with self.assertRaises(AutoIndexQueueError):
            create_draft(self.db,**self.args)

    def test_existing_unversioned_store_not_replaced(self):
        self.db.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.db)) as con:
            con.execute("CREATE TABLE other_file(data TEXT)")
        with self.assertRaises(AutoIndexQueueError):
            create_draft(self.db,**self.args)
        with closing(sqlite3.connect(self.db)) as con:
            self.assertIsNotNone(con.execute(
                "SELECT name FROM sqlite_master WHERE name='other_file'"
            ).fetchone())


if __name__=="__main__":
    unittest.main()
