import tempfile
from pathlib import Path
from unittest.mock import patch
from tests.test_incremental_job_queue import DurableQueueTests
from rag.runtime.incremental_job_queue import acknowledge_staged_bundle, inspect_job_queue
from tests.test_incremental_bundle_validate import fixture
from rag.index.manifest import IndexManifest,ManifestEntry,ManifestIndexKind,save_index_manifest
import sqlite3
from contextlib import closing

class OfflineStagingReceiptTests(DurableQueueTests):
    def make_stage(self):
        folder=Path(self.temp.name)/"staging"/"build-fixture"
        folder.mkdir(parents=True)
        fixture(folder)
        with closing(sqlite3.connect(folder/"rag_index.sqlite3")) as db:
            db.execute("UPDATE rag_documents SET project_id='codebridge', path='sample.py', sha256=?", (self.sha,))
            db.execute("UPDATE rag_chunks SET project_id='codebridge', path='sample.py'")
            db.commit()
        save_index_manifest(folder/"rag-index-manifest.json",IndexManifest((
            ManifestEntry(project_id="codebridge",index_kind=ManifestIndexKind.TEXT,
                path="sample.py",size=5,mtime_ns=1,sha256=self.sha,chunk_ids=("c1",),model_version="fixture"),
        )))
        from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local
        q=open_qdrant_local(folder/"qdrant")
        try:
            q.set_payload("text",payload={"project_namespace":"codebridge"},points=[42])
        finally: close_qdrant_local(q)
        return folder

    def test_valid_receipt_is_offline_only(self):
        self.enqueue(queue_enabled=True,now_epoch=140)
        claim=self.claim(now_epoch=141)
        stage=self.make_stage()
        result=acknowledge_staged_bundle(self.db,self.root,claim["job_id"],
            claim["lease_token"],stage,approved_paths=("sample.py",),
            now_epoch=142,queue_enabled=True)
        self.assertEqual(result["state"],"STAGED_OFFLINE_VALIDATED")
        self.assertTrue(result["acknowledged"])
        self.assertFalse(result["active_index_updated"])
        self.assertFalse(result["safe_to_publish"])
        self.assertEqual(inspect_job_queue(self.db)["by_state"],{"STAGED_OFFLINE_VALIDATED":1})
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM staging_receipts").fetchone()[0],1)
        self.assertEqual(acknowledge_staged_bundle(self.db,self.root,claim["job_id"],
            claim["lease_token"],stage,approved_paths=("sample.py",),
            now_epoch=143,queue_enabled=True)["state"],"STALE_OR_EXPIRED_LEASE")

    def test_invalid_bundle_leaves_claim_intact(self):
        self.enqueue(queue_enabled=True,now_epoch=140)
        claim=self.claim(now_epoch=141)
        stage=Path(self.temp.name)/"staging"/"build-empty"
        stage.mkdir(parents=True)
        result=acknowledge_staged_bundle(self.db,self.root,claim["job_id"],
            claim["lease_token"],stage,approved_paths=("sample.py",),
            now_epoch=142,queue_enabled=True)
        self.assertEqual(result["state"],"STAGING_INVALID")
        self.assertEqual(inspect_job_queue(self.db)["by_state"],{"CLAIMED":1})

    def test_expired_lease_cannot_ack(self):
        self.enqueue(queue_enabled=True,now_epoch=140)
        claim=self.claim(now_epoch=141,lease_seconds=10)
        result=acknowledge_staged_bundle(self.db,self.root,claim["job_id"],
            claim["lease_token"],Path(self.temp.name)/"staging"/"build-a",
            approved_paths=("sample.py",),now_epoch=152,queue_enabled=True)
        self.assertEqual(result["state"],"STALE_OR_EXPIRED_LEASE")



    def test_schema_migration_preserves_existing_job(self):
        self.enqueue(queue_enabled=True,now_epoch=140)
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("PRAGMA user_version=1")
            sql=db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
            old=sql.replace(",'STAGED_OFFLINE_VALIDATED'","")
            db.execute("ALTER TABLE jobs RENAME TO jobs_new")
            db.execute(old)
            db.execute("INSERT INTO jobs SELECT * FROM jobs_new")
            db.execute("DROP TABLE jobs_new")
            db.commit()
        self.assertEqual(inspect_job_queue(self.db)["total"],1)
        claim=self.claim(now_epoch=141)
        self.assertEqual(claim["state"],"CLAIMED_FOR_OFFLINE_STAGING")
        stage=self.make_stage()
        result=acknowledge_staged_bundle(self.db,self.root,claim["job_id"],
            claim["lease_token"],stage,approved_paths=("sample.py",),
            now_epoch=142,queue_enabled=True)
        self.assertEqual(result["state"],"STAGED_OFFLINE_VALIDATED")
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0],2)
