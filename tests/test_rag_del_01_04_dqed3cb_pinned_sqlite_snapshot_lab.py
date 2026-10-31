"""DQ-E-D-3C-B: real worker reads only pinned private TEMP SQLite namespace."""
from contextlib import closing
from hashlib import sha256
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json
import sqlite3
import subprocess
import sys

from rag.contracts import SearchQuery, SourceType
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.knowledge_deletion_private_read_session_lab import private_read_session_lab
from rag.runtime.knowledge_deletion_semantic_dispatch_lab import dispatch_semantic_already_locked_lab
from rag.runtime.knowledge_deletion_semantic_request_lab import PinnedSemanticRequestV1
from rag.runtime.production_generation_lock import production_generation_lock
from rag.runtime import isolated_project_worker


class RealWorkerPinnedSQLiteReadTests(TestCase):
    def setUp(self):
        temporary=TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.rag=self.root/"CodeBridge"/"rag"
        self.rag.mkdir(parents=True)
        self.catalog=self.root/"project-indexes.json"
        self.db=self.root/"generations"/"private_db"/"rag_index.sqlite3"
        self.db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("CREATE TABLE rag_documents(project_id TEXT,path TEXT)")
            cn.executemany("INSERT INTO rag_documents VALUES (?,?)",[
                ("private-lab","private/src/a.py"),
                ("private-lab","private/src/b.py"),
                ("another-lab","foreign/secret.py"),
            ])
            cn.commit()
        self.manifest=self.db.with_name("rag-index-manifest.json")
        self.manifest.write_text('{"fake":"private"}',encoding="utf-8")
        self.catalog.write_text(json.dumps({
            "schema_version":1,"projects":{"private-lab":{
                "project_id":"private-lab","enabled":True,
                "source_revision":"test-revision",
                "generation_directory":str(self.db.parent.resolve()),
                "sqlite_sha256":sha256(self.db.read_bytes()).hexdigest(),
                "manifest_sha256":sha256(self.manifest.read_bytes()).hexdigest(),
            }}
        }),encoding="utf-8")
        self.query=SearchQuery(
            query="code privacy",project_id="private-lab",top_k=2,
            source_types=(SourceType.CODE,),
        )
        self.route=QueryRoute.CODE

    def patch_root(self):
        return patch(
            "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
            return_value=self.rag/"rag_index.sqlite3",
        )

    def session(self):
        return private_read_session_lab(
            "private-lab",catalog_file=self.catalog,
            sqlite_path=self.db,manifest_path=self.manifest,
            generation_guard_factory=lambda:production_generation_lock(
                exclusive=False,channel="generation",
            ),
            semantic_guard_factory=lambda:production_generation_lock(
                exclusive=True,channel="semantic",
            ),
            semantic=True,laboratory_mode=True,operator_approved=True,
        )

    def request(self,pin):
        def build(query,route,envelope):
            return PinnedSemanticRequestV1.parse({
                "schema_version":1,"pin":envelope.to_payload(),
                "query":query.query,"route":route.value,"top_k":query.top_k,
                "source_types":[v.value for v in query.source_types],
                "path_filter":None,"branch":None,
            })
        return dispatch_semantic_already_locked_lab(
            self.query,self.route,pin=pin,catalog_file=self.catalog,
            executor=build,laboratory_mode=True,operator_approved=True,
        )

    def child(self,payload,*,root=None,mode="--pinned-scratch-snapshot"):
        return subprocess.run(
            [sys.executable,"-m","rag.runtime.isolated_project_worker",
             mode,str(root or self.root)],
            cwd=str(Path(__file__).resolve().parents[1]),
            input=json.dumps(payload)+"\n",capture_output=True,text=True,
            timeout=10,
        )

    def test_real_worker_reads_only_selected_namespace_and_not_foreign(self):
        with self.patch_root():
            with self.session() as pin:
                req=self.request(pin)
                child=self.child(req.to_payload())
                self.assertEqual(child.returncode,0,child.stderr)
                reply=json.loads(child.stdout)
                self.assertEqual(reply["state"],"LAB_PINNED_SQLITE_NAMESPACE_READ_ONLY")
                self.assertEqual(reply["matching_private_document_count"],2)
                self.assertEqual(reply["project_id"],"private-lab")
                self.assertEqual(reply["generation_id"],"private_db")
                self.assertEqual(reply["nonce"],req.pin.nonce)
                self.assertEqual(reply["request_sha256"],req.request_digest())
                for field in ("model_executed","qdrant_accessed",
                              "activation_authorized","operational_use_allowed",
                              "parent_locks_attested_by_worker"):
                    self.assertFalse(reply[field])

    def test_scratch_snapshot_branch_does_not_use_model_or_registered_resolver(self):
        with self.patch_root():
            with self.session() as pin:
                req=self.request(pin)
                result=StringIO()
                with (
                    patch.object(sys,"argv",["worker","--pinned-scratch-snapshot",str(self.root)]),
                    patch.object(sys,"stdin",StringIO(json.dumps(req.to_payload())+"\n")),
                    patch.object(sys,"stdout",result),
                    patch.object(isolated_project_worker,"resolve_isolated_project",
                                 side_effect=AssertionError("real project resolver called")),
                    patch.object(isolated_project_worker,"search_persistent_semantic",
                                 side_effect=AssertionError("model was called")),
                ):
                    isolated_project_worker.main()
                self.assertEqual(
                    json.loads(result.getvalue())["matching_private_document_count"],2
                )

    def test_change_in_sqlite_bytes_is_refused_even_if_row_count_same(self):
        with self.patch_root():
            with self.session() as pin:
                req=self.request(pin)
                original=self.db.read_bytes()
                try:
                    # Changed SQLite bytes, same document count, no valid SHA pin.
                    with closing(sqlite3.connect(self.db)) as cn:
                        cn.execute("UPDATE rag_documents SET path=? WHERE project_id=?",
                                   ("new-value","another-lab"))
                        cn.commit()
                    child=self.child(req.to_payload())
                    self.assertNotEqual(child.returncode,0)
                    self.assertFalse(child.stdout.strip())
                finally:
                    self.db.write_bytes(original)

    def test_changed_manifest_or_source_revision_prevents_snapshot(self):
        with self.patch_root():
            with self.session() as pin:
                req=self.request(pin)
                original=self.manifest.read_bytes()
                try:
                    self.manifest.write_text('{"tampered":true}',encoding="utf-8")
                    self.assertNotEqual(self.child(req.to_payload()).returncode,0)
                finally:
                    self.manifest.write_bytes(original)

    def test_request_from_another_project_or_wrong_generation_rejected(self):
        with self.patch_root():
            with self.session() as pin:
                req=self.request(pin)
                for change in (
                    {"project_id":"another-lab"},{"generation_id":"nonexistent"},
                    {"generation_id":"../etc"},
                ):
                    with self.subTest(change=change):
                        row=req.to_payload()
                        row["pin"]={**row["pin"],**change}
                        result=self.child(row)
                        self.assertNotEqual(result.returncode,0)

    def test_real_or_non_temp_catalog_not_accepted_even_with_valid_scratch_pin(self):
        with self.patch_root():
            with self.session() as pin:
                req=self.request(pin)
                child=self.child(req.to_payload(),root=Path.home())
                self.assertNotEqual(child.returncode,0)
                self.assertFalse(child.stdout.strip())

    def test_no_sqlite_write_and_parent_session_preserves_catalog(self):
        original=(self.db.read_bytes(),self.manifest.read_bytes(),
                  self.catalog.read_bytes())
        with self.patch_root():
            with self.session() as pin:
                req=self.request(pin)
                self.assertEqual(self.child(req.to_payload()).returncode,0)
        self.assertEqual(
            (self.db.read_bytes(),self.manifest.read_bytes(),self.catalog.read_bytes()),
            original,
        )

    def test_unreconciled_journal_blocks_child_even_when_rolled_back(self):
        with self.patch_root():
            with self.session() as pin:
                request=self.request(pin)
                journal=self.root/"rag-del-1234567890abcdef1234567890abcdef.journal.json"
                journal.write_text(
                    '{"state":"ROLLED_BACK","synthetic":true}',encoding="utf-8",
                )
                try:
                    child=self.child(request.to_payload())
                    self.assertNotEqual(child.returncode,0)
                    self.assertIn("unreconciled scratch deletion journal",child.stderr)
                    self.assertTrue(journal.exists())
                finally:
                    journal.unlink()

    def test_detached_worker_still_rejects_preexisting_scratch_journal(self):
        with self.patch_root():
            with self.session() as pin:
                request=self.request(pin)
        journal=self.root/"rag-del-deadbeef.journal.json"
        journal.write_text('{"state":"PREPARED"}',encoding="utf-8")
        child=self.child(request.to_payload())
        self.assertNotEqual(child.returncode,0)
        self.assertIn("unreconciled scratch deletion journal",child.stderr)
        self.assertTrue(journal.exists())

    def test_journal_appearing_during_worker_hash_validation_is_refused(self):
        from rag.runtime.knowledge_deletion_pin_ipc_lab import (
            verify_private_pin_envelope_lab, PinEnvelopeLabError,
        )
        from rag.runtime import knowledge_deletion_pin_ipc_lab as pin_mod
        real_sha=pin_mod._sha
        injected=[False]
        journal=self.root/"rag-del-race.journal.json"
        def injected_sha(path):
            result=real_sha(path)
            # After the initial catalog check, create the journal during
            # the last hash verification before the worker returns success.
            if not injected[0] and Path(path)==self.catalog:
                injected[0]=True
                journal.write_text('{"state":"PREPARED"}',encoding="utf-8")
            return result
        with self.patch_root():
            with self.session() as pin:
                request=self.request(pin)
                try:
                    with patch.object(pin_mod,"_sha",side_effect=injected_sha):
                        with self.assertRaisesRegex(PinEnvelopeLabError,"journal appeared"):
                            verify_private_pin_envelope_lab(
                                request.pin,catalog_file=self.catalog,
                                laboratory_mode=True,
                            )
                    self.assertTrue(injected[0])
                finally:
                    journal.unlink(missing_ok=True)

    def test_redirected_generations_root_rejected_if_symlink_is_permitted(self):
        from rag.runtime.knowledge_deletion_pin_ipc_lab import (
            verify_private_pin_envelope_lab, PinEnvelopeLabError,
        )
        with self.patch_root():
            with self.session() as pin:
                request=self.request(pin)
                # Renaming the real directory within scratch is reversible;
                # link to it is unsafe regardless of contained target.
                original=self.root/"generations"
                moved=self.root/"archived_generations"
                original.rename(moved)
                try:
                    try:
                        original.symlink_to(moved,target_is_directory=True)
                    except (OSError,NotImplementedError) as exc:
                        self.skipTest("Windows symlink privilege unavailable: "+str(exc))
                    with self.assertRaisesRegex(PinEnvelopeLabError,"redirected"):
                        verify_private_pin_envelope_lab(
                            request.pin,catalog_file=self.catalog,laboratory_mode=True,
                        )
                finally:
                    if original.is_symlink():
                        original.unlink()
                    moved.rename(original)
