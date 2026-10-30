"""Temporary RAG_DEL_01 receipt assembly and resolver handoff."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json,sys
from rag.runtime.knowledge_deletion_bundle import prepare_deletion_review_bundle
from rag.runtime.knowledge_deletion_assemble_lab import assemble_lab_deletion_generation,DeletionGenerationAssemblyError
from rag.runtime.knowledge_deletion_generation import verify_deletion_generation
from rag.runtime.isolated_project_index import resolve_isolated_project

class AssemblyLabTests(TestCase):
    def setUp(self):
        t=TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.tid="b"*32
        self.stage=self.root/"generations"/("del_"+self.tid)
        self.stage.mkdir(parents=True)
        self.snapshot=self.root/"snapshots"/("source_"+self.tid)
        self.snapshot.mkdir(parents=True)
        (self.stage/"rag_index.sqlite3").write_bytes(b"sqlite")
        (self.stage/"rag-index-manifest.json").write_bytes(b"manifest")
        (self.stage/"qdrant").mkdir()
        (self.stage/"qdrant"/"segment.bin").write_bytes(b"fake-closed-qdrant")
        self.revision="a"*64
        self.preview={
           "mode":"READ_ONLY_REMOVAL_PREVIEW","project_id":"demo",
           "generation":"auto_baseline","source_revision":self.revision,
           "review_sha256":"c"*64,"chunks_to_preserve":2,
           "deletion_authorized":False}
        self.evidence={
           "schema_version":1,"state":"EVIDENCE_ONLY_NOT_ACTIVATABLE",
           "project_id":"demo","baseline_generation":"auto_baseline",
           "selection_sha256":"c"*64,"receipt_sha256":"d"*64,
           "activation_authorized":False}
        patcher=patch("rag.runtime.knowledge_deletion_bundle.inspect_deletion_candidate_evidence",
                      return_value=self.evidence)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.bundle=prepare_deletion_review_bundle(self.stage)
    def assemble(self,**kwargs):
        return assemble_lab_deletion_generation(
           self.stage,self.snapshot,"demo",self.revision,self.tid,
           self.preview,self.bundle,**{"laboratory_mode":True,**kwargs})
    def test_roundtrip_to_resolver(self):
        row=self.assemble()
        self.assertFalse(row["activation_authorized"])
        self.assertEqual(verify_deletion_generation(
            row,"demo",self.stage,self.snapshot,self.revision)["vectors_verified"],2)
        row["python_executable"]=sys.executable
        with patch("rag.runtime.isolated_project_index._entries",return_value={"demo":row}),\
             patch("rag.runtime.isolated_project_index._workspace_root",return_value=self.root):
            index=resolve_isolated_project("demo")
        self.assertEqual(index.generation,"del_"+self.tid)
    def test_requires_laboratory_mode(self):
        with self.assertRaises(PermissionError): self.assemble(laboratory_mode=False)
    def test_rejects_replay(self):
        self.assemble()
        with self.assertRaises(DeletionGenerationAssemblyError): self.assemble()
    def test_real_verified_lab_swap_then_rollback(self):
        from rag.runtime.knowledge_deletion_verified_swap_lab import laboratory_verified_swap
        from rag.runtime.knowledge_deletion_swap_lab import laboratory_rollback
        row=self.assemble()
        row["python_executable"]=sys.executable
        catalog=self.root/"project-indexes.json"
        pointer=self.root/"active-generation.json"
        catalog.write_text(json.dumps({
            "schema_version":1,
            "projects":{"demo":{"project_id":"demo","enabled":True,
                                "source_revision":"e"*64,
                                "generation_directory":"previous-generation"},
                        "other":{"project_id":"other","enabled":True,
                                 "source_revision":"f"*64,
                                 "generation_directory":"unrelated"}}}))
        pointer.write_text(json.dumps({"schema_version":1,"generation":"public"}))
        original=catalog.read_bytes()
        public=pointer.read_bytes()
        switched=laboratory_verified_swap("demo","e"*64,row,
            catalog_file=catalog,public_pointer=pointer,
            operator_approved=True,laboratory_mode=True)
        self.assertEqual(switched["state"],"LAB_SWAP_ACTIVE")
        self.assertEqual(pointer.read_bytes(),public)
        after=json.loads(catalog.read_text())
        self.assertEqual(after["projects"]["demo"]["index_family"],"RAG_DEL_01")
        self.assertEqual(after["projects"]["other"]["source_revision"],"f"*64)
        rolled=laboratory_rollback(switched["transaction"],
            catalog_file=catalog,public_pointer=pointer,
            operator_approved=True,laboratory_mode=True)
        self.assertEqual(rolled["state"],"LAB_ROLLBACK_COMPLETE")
        self.assertEqual(catalog.read_bytes(),original)
        self.assertEqual(pointer.read_bytes(),public)

    def test_interrupted_receipt_write_quarantines_stage(self):
        from rag.runtime.knowledge_deletion_assemble_lab import os as module_os
        native_open=module_os.open
        calls=[0]
        def fail_second_open(*args,**kwargs):
            calls[0]+=1
            if calls[0]==2:
                raise OSError("simulated disk interruption")
            return native_open(*args,**kwargs)
        with patch("rag.runtime.knowledge_deletion_assemble_lab.os.open",
                   side_effect=fail_second_open):
            with self.assertRaises(OSError):
                self.assemble()
        self.assertTrue((self.stage/"progress.json").exists())
        self.assertFalse((self.stage/"deletion-generation-receipt.json").exists())
        with self.assertRaises(DeletionGenerationAssemblyError):
            self.assemble()

    def test_changed_qdrant_since_review_refused(self):
        (self.stage/"qdrant"/"segment.bin").write_bytes(b"modified")
        with self.assertRaises(Exception): self.assemble()
    def test_review_mismatch_refused(self):
        self.preview["review_sha256"]="f"*64
        with self.assertRaises(DeletionGenerationAssemblyError): self.assemble()
