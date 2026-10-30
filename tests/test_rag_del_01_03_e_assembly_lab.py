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
