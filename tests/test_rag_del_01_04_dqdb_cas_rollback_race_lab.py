"""RAG-DEL-01.04-DQ-D-B: full scratch writer fence vs private readers/CAS."""
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json
import sqlite3
import subprocess
import sys

from rag.runtime.knowledge_deletion_writer_fence_lab import laboratory_writer_fence
from rag.runtime.knowledge_deletion_swap_lab import (
    laboratory_swap, laboratory_rollback, DeletionSwapError,
)
from rag.runtime.knowledge_deletion_private_read_session_lab import private_read_session_lab
from rag.runtime.knowledge_deletion_bounded_catalog_lab import LaboratoryCatalogUnsafe
from rag.runtime.production_generation_lock import (
    production_generation_lock, ProductionGenerationBusy,
)


_READER_CHILD=r"""
import sys
from pathlib import Path
from unittest.mock import patch
from rag.runtime.knowledge_deletion_private_read_session_lab import private_read_session_lab
from rag.runtime.production_generation_lock import production_generation_lock,ProductionGenerationBusy
root=Path(sys.argv[1])
sqlite=root/"generations"/"old_generation"/"rag_index.sqlite3"
with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
           return_value=root/"CodeBridge"/"rag"/"rag_index.sqlite3"):
    try:
        with private_read_session_lab(
            "demo",catalog_file=root/"project-indexes.json",
            sqlite_path=sqlite,manifest_path=sqlite.with_name("rag-index-manifest.json"),
            generation_guard_factory=lambda:production_generation_lock(
                exclusive=False,channel="generation"),
            semantic_guard_factory=lambda:production_generation_lock(
                exclusive=True,channel="semantic"),
            semantic=True,laboratory_mode=True,operator_approved=True,
        ) as pinned:
            print("READER_HELD:"+pinned.generation,flush=True)
            sys.stdin.readline()
    except ProductionGenerationBusy:
        print("READER_BUSY",flush=True)
"""


_QUEUE_CHILD=r"""
import sqlite3,sys
from pathlib import Path
db=sqlite3.connect(Path(sys.argv[1]),timeout=0.04,isolation_level=None)
try:
    db.execute("BEGIN IMMEDIATE")
    print("QUEUE_ACQUIRED")
    db.execute("ROLLBACK")
except sqlite3.OperationalError:
    print("QUEUE_BUSY")
finally:
    db.close()
"""


class PrivateCasReaderRaceTests(TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.rag=self.root/"CodeBridge"/"rag"
        self.rag.mkdir(parents=True)
        self.catalog=self.root/"project-indexes.json"
        self.pointer=self.root/"active-generation.json"
        self.queue=self.root/"auto"/"jobs"/"auto_index_jobs.sqlite3"
        self.queue.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.queue)) as conn:
            conn.execute("CREATE TABLE auto_worker_lease "
                "(singleton INTEGER PRIMARY KEY,job_id TEXT,lease_token TEXT,"
                "lease_until_epoch REAL,generation INTEGER)")
            conn.execute("INSERT INTO auto_worker_lease VALUES (1,NULL,NULL,NULL,5)")
            conn.execute("CREATE TABLE auto_jobs(job_id TEXT,state TEXT)")
            conn.execute("PRAGMA user_version=1")
            conn.commit()
        self.old=self.make_generation("old_generation","old protected evidence")
        self.new=self.make_generation("new_generation","new candidate evidence")
        self.first=self.row_for("old_generation","revision-old")
        self.candidate=self.row_for("new_generation","revision-new")
        self.other={"project_id":"other","enabled":True,"source_revision":"other",
                    "generation_directory":"unrelated"}
        self.catalog.write_text(json.dumps({
            "schema_version":1,"projects":{"demo":self.first,"other":self.other}
        }),encoding="utf-8")
        self.pointer.write_text(
            '{"schema_version":1,"generation":"public-production-untouched"}',
            encoding="utf-8",
        )
        self.before=self.catalog.read_bytes()
        self.public=self.pointer.read_bytes()

    def make_generation(self,name,content):
        folder=self.root/"generations"/name
        folder.mkdir(parents=True)
        db=folder/"rag_index.sqlite3"
        with closing(sqlite3.connect(db)) as conn:
            conn.execute("CREATE TABLE rag_documents "
                "(project_id TEXT,path TEXT,source_type TEXT)")
            conn.execute("INSERT INTO rag_documents VALUES ('demo',?,'CODE')",
                         (content,))
            conn.commit()
        (folder/"rag-index-manifest.json").write_text(
            json.dumps({"synthetic":content}),encoding="utf-8",
        )
        return db

    def row_for(self,name,revision):
        db=self.root/"generations"/name/"rag_index.sqlite3"
        return {
            "project_id":"demo","enabled":True,"source_revision":revision,
            "generation_directory":str(db.parent.resolve()),
            "sqlite_sha256":sha256(db.read_bytes()).hexdigest(),
            "manifest_sha256":sha256(
                db.with_name("rag-index-manifest.json").read_bytes()
            ).hexdigest(),
        }

    def patch_root(self):
        return patch(
            "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
            return_value=self.rag/"rag_index.sqlite3",
        )

    def fence(self):
        return laboratory_writer_fence(
            self.queue,
            lambda: production_generation_lock(
                exclusive=True,channel="generation",
            ),
            lambda: production_generation_lock(
                exclusive=True,channel="semantic",
            ),
            laboratory_mode=True,operator_approved=True,
        )

    def swap(self,*,revision="revision-old",fail_at=None):
        return laboratory_swap(
            "demo",revision,self.candidate,
            catalog_file=self.catalog,public_pointer=self.pointer,
            operator_approved=True,laboratory_mode=True,_fail_at=fail_at,
        )

    def rollback(self,transaction):
        return laboratory_rollback(
            transaction,catalog_file=self.catalog,public_pointer=self.pointer,
            laboratory_mode=True,operator_approved=True,
        )

    def old_reader(self):
        return private_read_session_lab(
            "demo",catalog_file=self.catalog,sqlite_path=self.old,
            manifest_path=self.old.with_name("rag-index-manifest.json"),
            generation_guard_factory=lambda:production_generation_lock(
                exclusive=False,channel="generation",
            ),
            semantic_guard_factory=lambda:production_generation_lock(
                exclusive=True,channel="semantic",
            ),
            semantic=True,laboratory_mode=True,operator_approved=True,
        )

    def child(self,script,*args):
        return subprocess.Popen(
            [sys.executable,"-c",script,*map(str,args)],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True,
        )

    def test_reader_blocks_writer_cutover_until_released_then_cas_and_rollback(self):
        child=self.child(_READER_CHILD,self.root)
        try:
            self.assertEqual(
                child.stdout.readline().strip(),"READER_HELD:old_generation",
                child.stderr.read() if child.poll() is not None else "",
            )
            with self.patch_root():
                with self.assertRaises(ProductionGenerationBusy):
                    with self.fence():
                        self.fail("cannot swap while private reader pins generation")
            self.assertEqual(self.catalog.read_bytes(),self.before)
            self.assertFalse(list(self.root.glob("rag-del-*.journal.json")))
        finally:
            if child.poll() is None:
                try:
                    child.communicate(input="\n",timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.communicate(timeout=5)
        self.assertEqual(child.returncode,0)
        with self.patch_root():
            with self.fence() as evidence:
                self.assertEqual(evidence["lock_order"],
                                 ["generation","semantic","queue"])
                result=self.swap()
                self.assertEqual(result["state"],"LAB_SWAP_ACTIVE")
                self.assertFalse(result["operational_use_allowed"])
                self.assertEqual(self.pointer.read_bytes(),self.public)
                self.assertEqual(
                    json.loads(self.catalog.read_text())["projects"]["other"],
                    self.other,
                )
                self.assertEqual(
                    self.rollback(result["transaction"])["state"],
                    "LAB_ROLLBACK_COMPLETE",
                )
        self.assertEqual(self.catalog.read_bytes(),self.before)
        self.assertEqual(self.pointer.read_bytes(),self.public)
        # Historical journal is not silently archived/deleted by a rollback.
        with self.patch_root():
            with self.assertRaises(LaboratoryCatalogUnsafe):
                with self.old_reader():
                    pass

    def test_active_writer_fence_blocks_new_reader_and_queue_reservation(self):
        with self.patch_root():
            with self.fence():
                reader=self.child(_READER_CHILD,self.root)
                out,err=reader.communicate(timeout=10)
                self.assertEqual(reader.returncode,0,err)
                self.assertIn("READER_BUSY",out)
                waiter=self.child(_QUEUE_CHILD,self.queue)
                out,err=waiter.communicate(timeout=10)
                self.assertEqual(waiter.returncode,0,err)
                self.assertIn("QUEUE_BUSY",out)
            with self.old_reader() as pin:
                self.assertEqual(pin.generation,"old_generation")
        self.assertEqual(self.catalog.read_bytes(),self.before)

    def test_stale_cas_refused_before_any_journal_and_injected_failure_rolled_back(self):
        with self.patch_root():
            with self.fence():
                with self.assertRaises(ValueError):
                    self.swap(revision="stale-revision")
                self.assertEqual(self.catalog.read_bytes(),self.before)
                self.assertFalse(list(self.root.glob("rag-del-*.journal.json")))
                with self.assertRaisesRegex(DeletionSwapError,
                                            "injected post-switch"):
                    self.swap(fail_at="after")
                self.assertNotEqual(self.catalog.read_bytes(),self.before)
                journals=list(self.root.glob("rag-del-*.journal.json"))
                self.assertEqual(len(journals),1)
                tid=journals[0].name[len("rag-del-"):-len(".journal.json")]
                # Must not start another CAS with unresolved prior transaction.
                with self.assertRaises(DeletionSwapError):
                    self.swap(revision="revision-new")
                self.assertEqual(
                    self.rollback(tid)["state"],"LAB_ROLLBACK_COMPLETE",
                )
                self.assertEqual(self.rollback(tid)["state"],"ALREADY_ROLLED_BACK")
        self.assertEqual(self.catalog.read_bytes(),self.before)
        self.assertEqual(self.pointer.read_bytes(),self.public)
        self.assertEqual(json.loads(journals[0].read_text())["state"],
                         "ROLLED_BACK")
        with self.patch_root():
            with self.assertRaises(LaboratoryCatalogUnsafe):
                with self.old_reader():
                    pass