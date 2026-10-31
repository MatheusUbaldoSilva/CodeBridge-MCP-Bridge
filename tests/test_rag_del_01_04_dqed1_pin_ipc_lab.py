"""RAG-DEL-01.04-DQ-E-D-1: real subprocess validates TEMP pin IPC only."""
from contextlib import closing
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json
import sqlite3
import subprocess
import sys

from rag.runtime.knowledge_deletion_pin_ipc_lab import (
    PrivateReadPinEnvelopeV1, PinEnvelopeLabError,
    envelope_from_private_lab_pin, verify_private_pin_envelope_lab,
)
from rag.runtime.knowledge_deletion_private_read_session_lab import (
    private_read_session_lab, PrivateReadSessionLabError,
)
from rag.runtime.production_generation_lock import (
    production_generation_lock,
)


_WRITER=r"""
import sys
from pathlib import Path
from unittest.mock import patch
from rag.runtime.production_generation_lock import production_generation_lock,ProductionGenerationBusy
root=Path(sys.argv[1])
with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
           return_value=root/"CodeBridge"/"rag"/"rag_index.sqlite3"):
    try:
        with production_generation_lock(exclusive=True,channel="generation"):
            print("WRITER_ALLOWED")
    except ProductionGenerationBusy:
        print("WRITER_BUSY")
"""


class ParentChildPinEnvelopeTests(TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.rag=self.root/"CodeBridge"/"rag"
        self.rag.mkdir(parents=True)
        self.catalog=self.root/"project-indexes.json"
        self.old=self.make_generation("private_old","old document")
        self.other=self.make_generation("private_new","new document")
        self.row=self.registration(self.old,"source-old")
        self.write_catalog()

    def make_generation(self, name,content):
        folder=self.root/"generations"/name
        folder.mkdir(parents=True)
        db=folder/"rag_index.sqlite3"
        with closing(sqlite3.connect(db)) as cn:
            cn.execute("CREATE TABLE rag_documents(project_id TEXT,path TEXT)")
            cn.execute("INSERT INTO rag_documents VALUES (?,?)",("project-lab",content))
            cn.commit()
        (folder/"rag-index-manifest.json").write_text(
            json.dumps({"content":content}),encoding="utf-8",
        )
        return db

    def registration(self,db,revision):
        return {
            "project_id":"project-lab",
            "enabled":True,
            "source_revision":revision,
            "generation_directory":str(db.parent.resolve()),
            "sqlite_sha256":sha256(db.read_bytes()).hexdigest(),
            "manifest_sha256":sha256(
                db.with_name("rag-index-manifest.json").read_bytes()
            ).hexdigest(),
        }

    def write_catalog(self):
        self.catalog.write_text(json.dumps({
            "schema_version":1,
            "projects":{"project-lab":self.row},
        }),encoding="utf-8")

    def patch_root(self):
        return patch(
            "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
            return_value=self.rag/"rag_index.sqlite3",
        )

    def session(self,*,semantic=True):
        return private_read_session_lab(
            "project-lab",catalog_file=self.catalog,sqlite_path=self.old,
            manifest_path=self.old.with_name("rag-index-manifest.json"),
            generation_guard_factory=lambda:production_generation_lock(
                exclusive=False,channel="generation",
            ),
            semantic_guard_factory=lambda:production_generation_lock(
                exclusive=True,channel="semantic",
            ),
            semantic=semantic,laboratory_mode=True,operator_approved=True,
        )

    def child(self,payload,root=None):
        return subprocess.run(
            [sys.executable,"-m","rag.runtime.knowledge_deletion_pin_worker_lab",
             str(root or self.root)],
            input=json.dumps(payload),capture_output=True,text=True,timeout=10,
            cwd=str(Path(__file__).resolve().parents[1]),
        )

    def pin(self,session):
        return envelope_from_private_lab_pin(
            session,catalog_file=self.catalog,laboratory_mode=True,
        )

    def test_real_child_validates_exact_generation_without_any_model(self):
        original=self.catalog.read_bytes()
        with self.patch_root():
            with self.session() as session:
                envelope=self.pin(session)
                self.assertEqual(envelope.generation_id,"private_old")
                self.assertEqual(envelope.source_revision,"source-old")
                self.assertEqual(len(envelope.nonce),32)
                result=self.child(envelope.to_payload())
                self.assertEqual(result.returncode,0,result.stderr)
                body=json.loads(result.stdout)
                self.assertEqual(body["state"],"LAB_PIN_ENVELOPE_VALIDATED")
                self.assertEqual(body["generation_id"],"private_old")
                self.assertEqual(body["nonce"],envelope.nonce)
                self.assertFalse(body["parent_locks_attested_by_worker"])
                self.assertFalse(body["activation_authorized"])
                with self.assertRaises(FrozenInstanceError):
                    envelope.nonce="replaced"
        self.assertEqual(self.catalog.read_bytes(),original)

    def test_external_writer_denied_during_real_child_validation(self):
        with self.patch_root():
            with self.session() as session:
                envelope=self.pin(session)
                result=self.child(envelope.to_payload())
                self.assertEqual(result.returncode,0,result.stderr)
                writer=subprocess.run(
                    [sys.executable,"-c",_WRITER,str(self.root)],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    capture_output=True,text=True,timeout=10,
                )
                self.assertEqual(writer.returncode,0,writer.stderr)
                self.assertIn("WRITER_BUSY",writer.stdout)
            writer=subprocess.run(
                [sys.executable,"-c",_WRITER,str(self.root)],
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,text=True,timeout=10,
            )
            self.assertEqual(writer.returncode,0,writer.stderr)
            self.assertIn("WRITER_ALLOWED",writer.stdout)

    def test_new_generation_candidate_not_accepted_for_old_pin(self):
        with self.patch_root():
            with self.session() as session:
                envelope=self.pin(session)
        # The pin object cannot authorize a late child after catalog switch.
        self.row=self.registration(self.other,"source-new")
        self.write_catalog()
        reply=self.child(envelope.to_payload())
        self.assertNotEqual(reply.returncode,0)
        self.assertIn("fingerprint mismatch",reply.stderr)

    def test_manifest_tampering_refused_by_child_and_restored_for_parent(self):
        with self.patch_root():
            with self.session() as session:
                envelope=self.pin(session)
                manifest=self.old.with_name("rag-index-manifest.json")
                before=manifest.read_bytes()
                try:
                    manifest.write_text('{"tampered":true}',encoding="utf-8")
                    reply=self.child(envelope.to_payload())
                    self.assertNotEqual(reply.returncode,0)
                    self.assertIn("manifest_sha256 pin drift",reply.stderr)
                finally:
                    manifest.write_bytes(before)

    def test_child_rejects_cross_project_and_any_path_keys(self):
        with self.patch_root():
            with self.session() as session:
                payload=self.pin(session).to_payload()
                for change in (
                    {"project_id":"codebridge"},
                    {"project_id":"other-project"},
                    {"generation_id":"../outside"},
                    {"root":"C:/Users/anything"},
                    {"sqlite_path":"../../system.db"},
                ):
                    with self.subTest(change=change):
                        modified={**payload,**change}
                        self.assertNotEqual(self.child(modified).returncode,0)

    def test_schema_hash_and_nonce_fail_closed_in_worker(self):
        with self.patch_root():
            with self.session() as session:
                payload=self.pin(session).to_payload()
                for change in (
                    {"schema_version":2},{"schema_version":True},
                    {"sqlite_sha256":"0"*64},
                    {"catalog_sha256":"0"*64},
                    {"manifest_sha256":"0"*64},
                    {"nonce":"invalid"},
                    {"source_revision":"stale"},
                ):
                    with self.subTest(change=change):
                        self.assertNotEqual(
                            self.child({**payload,**change}).returncode,0,
                        )

    def test_no_envelope_outside_held_semantic_lock_or_after_close(self):
        with self.patch_root():
            with self.session(semantic=False) as lexical:
                with self.assertRaisesRegex(PinEnvelopeLabError,"active semantic"):
                    self.pin(lexical)
            with self.session() as semantic:
                self.pin(semantic)
            with self.assertRaisesRegex(PinEnvelopeLabError,"active semantic"):
                self.pin(semantic)

    def test_child_rejects_real_or_non_scratch_root(self):
        with self.patch_root():
            with self.session() as session:
                payload=self.pin(session).to_payload()
                self.assertNotEqual(
                    self.child(payload,root=Path.home()).returncode,0,
                )

    def test_separate_sessions_generate_distinct_nonce(self):
        with self.patch_root():
            with self.session() as a:
                first=self.pin(a).nonce
            with self.session() as b:
                second=self.pin(b).nonce
        self.assertNotEqual(first,second)

    def test_writer_denied_while_verified_child_is_still_alive(self):
        with self.patch_root():
            with self.session() as session:
                envelope=self.pin(session)
                proc=subprocess.Popen(
                    [sys.executable,"-m","rag.runtime.knowledge_deletion_pin_worker_lab",
                     str(self.root),"--hold-for-ack"],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,text=True,
                )
                try:
                    proc.stdin.write(json.dumps(envelope.to_payload())+"\n")
                    proc.stdin.flush()
                    self.assertEqual(proc.stdout.readline().strip(),
                                     "LAB_CHILD_VERIFIED")
                    writer=subprocess.run(
                        [sys.executable,"-c",_WRITER,str(self.root)],
                        cwd=str(Path(__file__).resolve().parents[1]),
                        capture_output=True,text=True,timeout=10,
                    )
                    self.assertEqual(writer.returncode,0,writer.stderr)
                    self.assertIn("WRITER_BUSY",writer.stdout)
                    self.assertIsNone(proc.poll())
                    output,error=proc.communicate(input="ACK\n",timeout=10)
                    self.assertEqual(proc.returncode,0,error)
                    result=json.loads(output.strip())
                    self.assertEqual(result["nonce"],envelope.nonce)
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.communicate(timeout=5)
            writer=subprocess.run(
                [sys.executable,"-c",_WRITER,str(self.root)],
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,text=True,timeout=10,
            )
            self.assertIn("WRITER_ALLOWED",writer.stdout)
