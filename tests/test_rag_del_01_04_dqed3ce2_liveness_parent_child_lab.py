"""DQ-E-D-3C-E-2: kill parent/child on Windows and verify scratch locks."""
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time

from rag.runtime.production_generation_lock import (
    production_generation_lock,ProductionGenerationBusy,
)
from rag.runtime.knowledge_deletion_bounded_catalog_lab import (
    bounded_catalog_mutex_lab,LaboratoryCatalogBusy,
)


_WRITER = r"""
from pathlib import Path
from unittest.mock import patch
from rag.runtime.production_generation_lock import production_generation_lock,ProductionGenerationBusy
import sys
root=Path(sys.argv[1])
with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
           return_value=root/"CodeBridge"/"rag"/"rag_index.sqlite3"):
    try:
        with production_generation_lock(exclusive=True,channel="generation"):
            print("WRITER_ALLOWED")
    except ProductionGenerationBusy:
        print("WRITER_BUSY")
"""


class ParentChildLivenessWin32LabTests(TestCase):
    def setUp(self):
        temporary=TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.rag=self.root/"CodeBridge"/"rag"
        self.rag.mkdir(parents=True)
        self.catalog=self.root/"project-indexes.json"
        self.db=self.root/"generations"/"private_liveness"/"rag_index.sqlite3"
        self.db.parent.mkdir(parents=True)
        self.vector_dir=self.db.parent/"qdrant"
        self.vector_dir.mkdir()
        self.vector=self.vector_dir/"vectors.bin"
        self.vector.write_bytes(b"qdrant-probe")
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("CREATE TABLE rag_documents(project_id TEXT,path TEXT)")
            cn.execute("INSERT INTO rag_documents VALUES ('private-lab','test.py')")
            cn.commit()
        self.manifest=self.db.with_name("rag-index-manifest.json")
        self.manifest.write_text('{"lab":true}',encoding="utf-8")
        self.catalog.write_text(json.dumps({
            "schema_version":1,"projects":{"private-lab":{
                "project_id":"private-lab","enabled":True,
                "source_revision":"liveness-v1",
                "generation_directory":str(self.db.parent.resolve()),
                "sqlite_sha256":sha256(self.db.read_bytes()).hexdigest(),
                "manifest_sha256":sha256(self.manifest.read_bytes()).hexdigest(),
            }}
        }),encoding="utf-8")
        self.before=(self.catalog.read_bytes(),self.db.read_bytes(),
                     self.manifest.read_bytes(),self.vector.read_bytes())

    def start_parent(self):
        return subprocess.Popen(
            [sys.executable,"-m",
             "rag.runtime.knowledge_deletion_liveness_parent_lab",
             str(self.root)],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,
        )

    def ready(self,proc):
        line=proc.stdout.readline().strip()
        self.assertTrue(line.startswith("PARENT_READY "),line)
        return int(line.split()[-1])

    def writer(self):
        return subprocess.run(
            [sys.executable,"-c",_WRITER,str(self.root)],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,text=True,timeout=8,
        )

    def patch_root(self):
        return patch(
            "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
            return_value=self.rag/"rag_index.sqlite3",
        )

    def assert_original_artifacts(self):
        self.assertEqual(
            (self.catalog.read_bytes(),self.db.read_bytes(),
             self.manifest.read_bytes(),self.vector.read_bytes()),
            self.before,
        )

    def test_clean_parent_ack_child_response_and_lock_release(self):
        parent=self.start_parent()
        try:
            child_pid=self.ready(parent)
            self.assertGreater(child_pid,0)
            self.assertIn("WRITER_BUSY",self.writer().stdout)
            result,error=parent.communicate(input="ACK\n",timeout=8)
            self.assertEqual(parent.returncode,0,error)
            self.assertIn("PARENT_CONFIRMED",result)
            self.assertIn("WRITER_ALLOWED",self.writer().stdout)
            self.assertFalse((self.root/"lab-child-termination.json").exists())
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)
        self.assert_original_artifacts()

    def test_killed_parent_closes_pipe_child_fails_and_locks_release(self):
        parent=self.start_parent()
        marker=self.root/"lab-child-termination.json"
        try:
            child_pid=self.ready(parent)
            self.assertIn("WRITER_BUSY",self.writer().stdout)
            parent.kill()
            parent.communicate(timeout=5)
            self.assertNotEqual(parent.returncode,0)
            for _ in range(150):
                if marker.exists(): break
                time.sleep(0.03)
            self.assertTrue(marker.is_file(),"orphan child did not detect parent EOF")
            self.assertIn(json.loads(marker.read_text())["state"],
                          {"PARENT_PIPE_CLOSED","PARENT_PROCESS_EXITED"})
            self.assertIn("WRITER_ALLOWED",self.writer().stdout)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)
        self.assert_original_artifacts()

    def test_killed_child_is_fail_closed_and_parent_unlocks(self):
        parent=self.start_parent()
        try:
            child_pid=self.ready(parent)
            self.assertIn("WRITER_BUSY",self.writer().stdout)
            os.kill(child_pid,signal.SIGTERM)
            out,err=parent.communicate(input="ACK\n",timeout=8)
            self.assertNotEqual(parent.returncode,0,(out,err))
            self.assertNotIn("PARENT_CONFIRMED",out)
            self.assertIn("WRITER_ALLOWED",self.writer().stdout)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)
        self.assert_original_artifacts()

    def test_vector_tamper_during_child_wait_rejected_after_ack(self):
        parent=self.start_parent()
        marker=self.root/"lab-child-termination.json"
        try:
            self.ready(parent)
            self.assertIn("WRITER_BUSY",self.writer().stdout)
            self.vector.write_bytes(b"DIFFERENT___")
            out,err=parent.communicate(input="ACK\n",timeout=8)
            self.assertNotEqual(parent.returncode,0,(out,err))
            self.assertNotIn("PARENT_CONFIRMED",out)
            self.assertTrue(marker.is_file())
            self.assertEqual(json.loads(marker.read_text())["state"],
                             "CHILD_VECTOR_DRIFT")
            self.assertIn("WRITER_ALLOWED",self.writer().stdout)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)
            self.vector.write_bytes(self.before[3])
        self.assert_original_artifacts()

    def test_wrong_ack_does_not_complete_semantic_session(self):
        parent=self.start_parent()
        try:
            self.ready(parent)
            out,err=parent.communicate(input="INVALID\n",timeout=8)
            self.assertNotEqual(parent.returncode,0,(out,err))
            self.assertNotIn("PARENT_CONFIRMED",out)
            self.assertIn("WRITER_ALLOWED",self.writer().stdout)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)

    def test_parent_rejects_non_scratch_root_before_spawn(self):
        parent=subprocess.run(
            [sys.executable,"-m",
             "rag.runtime.knowledge_deletion_liveness_parent_lab",
             str(Path.home())],
            cwd=str(Path(__file__).resolve().parents[1]),
            input="",capture_output=True,text=True,timeout=8,
        )
        self.assertNotEqual(parent.returncode,0)
        self.assertNotIn("PARENT_READY",parent.stdout)

    def test_parent_ack_deadline_releases_all_locks(self):
        parent=self.start_parent()
        try:
            self.ready(parent)
            self.assertIn("WRITER_BUSY",self.writer().stdout)
            # Parent must timeout on its own, not wait indefinitely on stdin.
            parent.wait(timeout=9)
            parent.communicate(timeout=3)
            self.assertNotEqual(parent.returncode,0)
            self.assertIn("WRITER_ALLOWED",self.writer().stdout)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)
        self.assert_original_artifacts()

    def test_child_refuses_existing_evidence_path_not_overwritten(self):
        marker=self.root/"lab-child-termination.json"
        marker.write_text('{"protected":true}',encoding="utf-8")
        parent=self.start_parent()
        try:
            self.ready(parent)
            parent.kill()
            parent.communicate(timeout=5)
            for _ in range(100):
                if self.writer().stdout.find("WRITER_ALLOWED")>=0: break
                time.sleep(0.02)
            self.assertEqual(marker.read_text(encoding="utf-8"),
                             '{"protected":true}')
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)
