"""DQ-E-D-3C-D: synthetic SearchResult callback under pinned private lock."""
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

from rag.contracts import SearchQuery, SearchResult, SourceMetadata, SourceType
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.knowledge_deletion_private_read_session_lab import private_read_session_lab
from rag.runtime.knowledge_deletion_semantic_injected_lab import (
    invoke_pinned_semantic_injected_lab, InjectedSemanticLabError,
)
from rag.runtime.production_generation_lock import production_generation_lock
from rag.runtime.knowledge_deletion_pin_ipc_lab import PinEnvelopeLabError


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


class PinnedSyntheticSemanticRunnerTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.rag=self.root/"CodeBridge"/"rag"
        self.rag.mkdir(parents=True)
        self.catalog=self.root/"project-indexes.json"
        self.db=self.root/"generations"/"private_stub"/"rag_index.sqlite3"
        self.db.parent.mkdir(parents=True)
        self.qdrant=self.db.parent/"qdrant"
        self.qdrant.mkdir()
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("CREATE TABLE rag_documents(project_id TEXT,path TEXT)")
            cn.execute("INSERT INTO rag_documents VALUES ('private-lab','src/a.py')")
            cn.commit()
        self.manifest=self.db.with_name("rag-index-manifest.json")
        self.manifest.write_text('{"stub":true}',encoding="utf-8")
        self.catalog.write_text(json.dumps({
            "schema_version":1,"projects":{"private-lab":{
                "project_id":"private-lab","enabled":True,
                "source_revision":"stub-revision",
                "generation_directory":str(self.db.parent.resolve()),
                "sqlite_sha256":sha256(self.db.read_bytes()).hexdigest(),
                "manifest_sha256":sha256(self.manifest.read_bytes()).hexdigest(),
            }}
        }),encoding="utf-8")
        self.query=SearchQuery(
            query="where is the private context",project_id="private-lab",top_k=2,
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

    def dispatch(self,pin,stub):
        return invoke_pinned_semantic_injected_lab(
            self.query,self.route,pin=pin,catalog_file=self.catalog,
            model_stub=stub,laboratory_mode=True,operator_approved=True,
        )

    def result(self,project="private-lab",stale=False):
        return SearchResult(
            chunk_id="scratch:1",document_id="scratch-doc",content="synthetic",
            metadata=SourceMetadata(
                project_id=project,source_type=SourceType.CODE,path="src/a.py",
            ),
            score=0.9,rank=1,retrieval_modes=("STUB",),stale=stale,
        )

    def test_injected_runner_receives_exact_search_storage_paths_under_lock(self):
        captured=[]
        def fake_model(query,route,*,_generation_paths):
            captured.append((_generation_paths,query,route))
            return (self.result(),)
        with self.patch_root():
            with self.session() as pin:
                with patch("rag.runtime.production_generation_lock.production_generation_lock",
                           side_effect=AssertionError("unwanted lock reentry")):
                    value=self.dispatch(pin,fake_model)
        self.assertEqual(len(value),1)
        paths,q,r=captured[0]
        self.assertEqual(paths.generation,"private_stub")
        self.assertEqual(paths.sqlite,self.db)
        self.assertEqual(paths.manifest,self.manifest)
        self.assertEqual(paths.qdrant,self.qdrant)
        self.assertEqual(q.project_id,"private-lab")
        self.assertEqual(r,QueryRoute.CODE)

    def test_foreign_project_and_stale_results_fail_closed(self):
        with self.patch_root():
            with self.session() as pin:
                for result in ((self.result(project="foreign"),),
                               (self.result(stale=True),),
                               [self.result()]):
                    with self.subTest(result=result):
                        with self.assertRaises(InjectedSemanticLabError):
                            self.dispatch(pin,lambda *args,**kwargs:result)

    def test_hash_tampering_during_callback_is_caught_and_restored(self):
        original=self.manifest.read_bytes()
        def changed(*args,**kwargs):
            self.manifest.write_text('{"changed":true}',encoding="utf-8")
            return (self.result(),)
        with self.patch_root():
            with self.session() as pin:
                try:
                    with self.assertRaises(PinEnvelopeLabError):
                        self.dispatch(pin,changed)
                finally:
                    self.manifest.write_bytes(original)

    def test_missing_qdrant_fails_before_invoking_stub(self):
        with self.patch_root():
            with self.session() as pin:
                self.qdrant.rmdir()
                try:
                    with self.assertRaisesRegex(InjectedSemanticLabError,"Qdrant"):
                        self.dispatch(pin,lambda *args,**kw:self.fail("stub invoked"))
                finally:
                    self.qdrant.mkdir()

    def test_no_approval_and_missing_stub_are_denied(self):
        with self.patch_root():
            with self.session() as pin:
                with self.assertRaises(TypeError):
                    self.dispatch(pin,None)
                with self.assertRaises(PermissionError):
                    invoke_pinned_semantic_injected_lab(
                        self.query,self.route,pin=pin,catalog_file=self.catalog,
                        model_stub=lambda *args:(),
                        laboratory_mode=True,operator_approved=False,
                    )

    def test_writer_is_busy_during_model_stub_then_allowed_after_session(self):
        def attempt_writer(*args,**kwargs):
            other=subprocess.run(
                [sys.executable,"-c",_WRITER,str(self.root)],
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,text=True,timeout=10,
            )
            self.assertEqual(other.returncode,0,other.stderr)
            self.assertIn("WRITER_BUSY",other.stdout)
            return (self.result(),)
        with self.patch_root():
            with self.session() as pin:
                self.assertEqual(len(self.dispatch(pin,attempt_writer)),1)
            other=subprocess.run(
                [sys.executable,"-c",_WRITER,str(self.root)],
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,text=True,timeout=10,
            )
            self.assertIn("WRITER_ALLOWED",other.stdout)

    def test_vector_receipt_is_deterministic_for_nested_files(self):
        from rag.runtime.knowledge_deletion_vector_tree_receipt_lab import (
            create_vector_tree_receipt_lab,verify_vector_tree_receipt_lab,
        )
        folder=self.qdrant/"collection"
        folder.mkdir()
        (folder/"z.vec").write_bytes(b"vector-z")
        (folder/"a.vec").write_bytes(b"vector-a")
        with self.patch_root():
            with self.session() as pin:
                from rag.runtime.knowledge_deletion_pin_ipc_lab import envelope_from_private_lab_pin
                envelope=envelope_from_private_lab_pin(
                    pin,catalog_file=self.catalog,laboratory_mode=True,
                )
                first=create_vector_tree_receipt_lab(
                    envelope,catalog_file=self.catalog,laboratory_mode=True,
                )
                second=create_vector_tree_receipt_lab(
                    envelope,catalog_file=self.catalog,laboratory_mode=True,
                )
                self.assertEqual(first,second)
                self.assertEqual(first.directories,("collection",))
                self.assertEqual(tuple(x.relative_path for x in first.files),
                                 ("collection/a.vec","collection/z.vec"))
                self.assertEqual(len(first.tree_sha256),64)
                self.assertEqual(
                    verify_vector_tree_receipt_lab(
                        first,envelope,catalog_file=self.catalog,
                        laboratory_mode=True,
                    )["file_count"],2,
                )

    def test_same_size_qdrant_vector_tamper_during_callback_is_rejected(self):
        from rag.runtime.knowledge_deletion_vector_tree_receipt_lab import (
            VectorTreeReceiptLabError,
        )
        vectors=self.qdrant/"collection"/"vectors.bin"
        vectors.parent.mkdir()
        vectors.write_bytes(b"ABCD")
        def tamper(*args,**kwargs):
            vectors.write_bytes(b"WXYZ") # same size but changed content
            return (self.result(),)
        with self.patch_root():
            with self.session() as pin:
                try:
                    with self.assertRaisesRegex(VectorTreeReceiptLabError,"drift"):
                        self.dispatch(pin,tamper)
                finally:
                    vectors.write_bytes(b"ABCD")

    def test_new_or_deleted_qdrant_file_during_callback_is_rejected(self):
        from rag.runtime.knowledge_deletion_vector_tree_receipt_lab import VectorTreeReceiptLabError
        source=self.qdrant/"primary.vec"
        source.write_bytes(b"old")
        def new(*args,**kwargs):
            (self.qdrant/"unregistered.vec").write_bytes(b"new")
            return (self.result(),)
        with self.patch_root():
            with self.session() as pin:
                try:
                    with self.assertRaises(VectorTreeReceiptLabError):
                        self.dispatch(pin,new)
                finally:
                    (self.qdrant/"unregistered.vec").unlink()
                def remove(*args,**kwargs):
                    source.unlink()
                    return (self.result(),)
                try:
                    with self.assertRaises(VectorTreeReceiptLabError):
                        self.dispatch(pin,remove)
                finally:
                    source.write_bytes(b"old")

    def test_empty_directory_changes_fingerprint(self):
        from rag.runtime.knowledge_deletion_vector_tree_receipt_lab import VectorTreeReceiptLabError
        def create_empty(*args,**kwargs):
            (self.qdrant/"new_empty_dir").mkdir()
            return (self.result(),)
        with self.patch_root():
            with self.session() as pin:
                try:
                    with self.assertRaises(VectorTreeReceiptLabError):
                        self.dispatch(pin,create_empty)
                finally:
                    (self.qdrant/"new_empty_dir").rmdir()

    def test_qdrant_symlink_to_external_directory_rejected_when_supported(self):
        from rag.runtime.knowledge_deletion_vector_tree_receipt_lab import VectorTreeReceiptLabError
        outside=self.root/"other_qdrant"
        outside.mkdir()
        (outside/"bad.vec").write_bytes(b"x")
        link=self.qdrant/"alias"
        try:
            link.symlink_to(outside,target_is_directory=True)
        except (OSError,NotImplementedError) as exc:
            self.skipTest("Windows symlink privilege unavailable: "+str(exc))
        try:
            with self.patch_root():
                with self.session() as pin:
                    with self.assertRaises(VectorTreeReceiptLabError):
                        self.dispatch(pin,lambda *a,**kw:(self.result(),))
        finally:
            link.unlink()

    def test_vector_receipt_wrong_nonce_is_refused(self):
        from dataclasses import replace
        from rag.runtime.knowledge_deletion_pin_ipc_lab import envelope_from_private_lab_pin
        from rag.runtime.knowledge_deletion_vector_tree_receipt_lab import (
            create_vector_tree_receipt_lab,verify_vector_tree_receipt_lab,
            VectorTreeReceiptLabError,
        )
        with self.patch_root():
            with self.session() as pin:
                envelope=envelope_from_private_lab_pin(
                    pin,catalog_file=self.catalog,laboratory_mode=True,
                )
                receipt=create_vector_tree_receipt_lab(
                    envelope,catalog_file=self.catalog,laboratory_mode=True,
                )
                forged=replace(envelope,nonce="0"*32)
                with self.assertRaisesRegex(VectorTreeReceiptLabError,"identity mismatch"):
                    verify_vector_tree_receipt_lab(
                        receipt,forged,catalog_file=self.catalog,
                        laboratory_mode=True,
                    )

    def test_vector_tree_size_limit_fails_closed_before_model_callback(self):
        from rag.runtime.knowledge_deletion_vector_tree_receipt_lab import VectorTreeReceiptLabError
        oversized=self.qdrant/"oversize.bin"
        oversized.write_bytes(b"a"*(16*1024*1024+1))
        try:
            with self.patch_root():
                with self.session() as pin:
                    with self.assertRaisesRegex(VectorTreeReceiptLabError,"limits exceeded"):
                        self.dispatch(pin,lambda *args,**kwargs:self.fail("stub invoked"))
        finally:
            oversized.unlink()
