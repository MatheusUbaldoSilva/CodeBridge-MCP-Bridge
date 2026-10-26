"""RAG-AUTO-03 canary activation/rollback tests: NEVER touch live catalog."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from rag.runtime.auto_index_canary import (
    AutoCanaryError,activate_auto_canary,rollback_auto_canary,
)
from rag.runtime.isolated_project_index import (
    IsolatedProjectUnavailable,resolve_isolated_project,
)
from rag.runtime.isolated_project_search import get_isolated_project_context
from test_rag_auto_03_generation import AutoGenerationTests


class AutoCanaryTests(unittest.TestCase):
    prepare=AutoGenerationTests.prepare

    def setUp(self):
        AutoGenerationTests.setUp(self)
        self.prepared=self.prepare()
        self.workspace=self.home/"CodeBridge-RAG-Workspace"
        self.catalog=self.home/"local"/"CodeBridge"/"rag"/"project-indexes.json"
        self.catalog.parent.mkdir(parents=True,exist_ok=True)
        self.pointer=self.catalog.parent/"active-generation.json"
        self.pointer.write_text(
            json.dumps({"schema_version":1,"generation":"unchanged_public_v1"}),
            encoding="utf-8",
        )
        self.initial={
            "schema_version":1,
            "projects":{"legacy-demo":{"enabled":False,"project_id":"legacy-demo"}},
        }
        self.catalog.write_text(json.dumps(self.initial,indent=2),encoding="utf-8")
        self.initial_bytes=self.catalog.read_bytes()

    def activate(self,**kwargs):
        params={
            "catalog_file":self.catalog,"public_pointer":self.pointer,
            "workspace":self.workspace,"python_executable":Path(sys.executable),
            "operator_approved":True,
            "confirmation":"RAG_AUTO_CANARY:"+self.project+":"+self.job,
        }
        params.update(kwargs)
        return activate_auto_canary(self.queue,self.job,**params)

    def rollback(self,**kwargs):
        params={
            "catalog_file":self.catalog,"public_pointer":self.pointer,
            "workspace":self.workspace,
            "operator_approved":True,
            "confirmation":"RAG_AUTO_CANARY_ROLLBACK:"+self.job,
        }
        params.update(kwargs)
        return rollback_auto_canary(self.job,**params)

    def test_activate_and_restore_original_catalog_bytes(self):
        before=self.pointer.read_bytes()
        activated=self.activate()
        self.assertEqual(activated["state"],"ISOLATED_CANARY_ACTIVE")
        self.assertEqual(self.pointer.read_bytes(),before)
        data=json.loads(self.catalog.read_text(encoding="utf-8"))
        self.assertEqual(data["projects"]["legacy-demo"],self.initial["projects"]["legacy-demo"])
        self.assertEqual(data["projects"][self.project]["index_family"],"RAG_AUTO_03")
        with (patch("rag.runtime.isolated_project_index.catalog_path",return_value=self.catalog),
              patch("rag.runtime.isolated_project_index._workspace_root",return_value=self.workspace)):
            index=resolve_isolated_project(self.project)
            self.assertEqual(index.source_root,Path(self.prepared["source_snapshot"]))
            self.assertTrue(index.sqlite.exists())
            from rag.runtime.auto_index_batch import inventory_auto_vectors
            chunk=inventory_auto_vectors(self.queue,self.job)["_rows"][0][0]
            context=get_isolated_project_context(project_id=self.project,chunk_ids=[chunk])
            self.assertEqual(context["count"],1)
            self.assertEqual(context["items"][0]["chunk_id"],chunk)
        reverted=self.rollback()
        self.assertEqual(reverted["state"],"RESTORED_PREVIOUS_CATALOG")
        self.assertEqual(self.catalog.read_bytes(),self.initial_bytes)
        self.assertEqual(self.pointer.read_bytes(),before)
        self.assertTrue(Path(self.prepared["generation"]).is_dir())
        self.assertTrue(Path(self.prepared["source_snapshot"]).is_dir())

    def test_missing_specific_operator_confirmation_rejected(self):
        with self.assertRaises(PermissionError):
            self.activate(operator_approved=False)
        with self.assertRaises(PermissionError):
            self.activate(confirmation="wrong")
        self.assertEqual(self.catalog.read_bytes(),self.initial_bytes)

    def test_register_never_overwrites_existing_project(self):
        self.catalog.write_text(json.dumps({
            "schema_version":1,"projects":{
                self.project:{"enabled":False,"project_id":self.project},
            },
        }),encoding="utf-8")
        old=self.catalog.read_bytes()
        with self.assertRaises(AutoCanaryError):
            self.activate()
        self.assertEqual(self.catalog.read_bytes(),old)

    def test_catalog_mutation_blocks_rollback(self):
        self.activate()
        data=json.loads(self.catalog.read_text(encoding="utf-8"))
        data["projects"]["third-party"]={"enabled":False}
        self.catalog.write_text(json.dumps(data),encoding="utf-8")
        with self.assertRaises(AutoCanaryError):
            self.rollback()

    def test_public_pointer_mutation_blocks_rollback(self):
        self.activate()
        self.pointer.write_text(
            json.dumps({"schema_version":1,"generation":"other_public_v1"}),
            encoding="utf-8",
        )
        with self.assertRaises(AutoCanaryError):
            self.rollback()

    def test_canary_metadata_tamper_fails_closed(self):
        self.activate()
        with (patch("rag.runtime.isolated_project_index.catalog_path",return_value=self.catalog),
              patch("rag.runtime.isolated_project_index._workspace_root",return_value=self.workspace)):
            receipt=Path(self.prepared["generation"])/"auto-generation-receipt.json"
            receipt.write_text("{}",encoding="utf-8")
            with self.assertRaises(IsolatedProjectUnavailable):
                resolve_isolated_project(self.project)

    def test_source_tamper_causes_context_rejection(self):
        self.activate()
        with (patch("rag.runtime.isolated_project_index.catalog_path",return_value=self.catalog),
              patch("rag.runtime.isolated_project_index._workspace_root",return_value=self.workspace)):
            from rag.runtime.auto_index_batch import inventory_auto_vectors
            chunk=inventory_auto_vectors(self.queue,self.job)["_rows"][0]
            source=Path(self.prepared["source_snapshot"])/chunk[4]
            source.write_bytes(b"tampered")
            with self.assertRaises(Exception):
                get_isolated_project_context(project_id=self.project,chunk_ids=[chunk[0]])

    def test_rollback_idempotent_after_success(self):
        self.activate()
        self.rollback()
        result=self.rollback()
        self.assertEqual(result["state"],"ALREADY_ROLLED_BACK")

    def test_reenable_after_rollback_preserves_original_backup(self):
        self.activate()
        self.rollback()
        again=self.activate()
        self.assertEqual(again["state"],"ISOLATED_CANARY_ACTIVE")
        data=json.loads(self.catalog.read_text(encoding="utf-8"))
        self.assertTrue(data["projects"][self.project]["enabled"])
        journal=json.loads(Path(again["journal"]).read_text(encoding="utf-8"))
        self.assertEqual(journal["activation_attempt"],2)
        self.assertEqual(Path(again["backup"]).read_bytes(),self.initial_bytes)
        self.rollback()
        self.assertEqual(self.catalog.read_bytes(),self.initial_bytes)

    def test_interrupted_before_replace_can_rollback(self):
        before=self.pointer.read_bytes()
        with self.assertRaisesRegex(AutoCanaryError,"injected failure before"):
            self.activate(_test_fail_at="before")
        self.assertEqual(self.catalog.read_bytes(),self.initial_bytes)
        restored=self.rollback()
        self.assertEqual(restored["state"],"ALREADY_ROLLED_BACK")
        self.assertEqual(self.pointer.read_bytes(),before)

    def test_interrupted_after_replace_can_rollback(self):
        before=self.pointer.read_bytes()
        with self.assertRaisesRegex(AutoCanaryError,"injected failure after"):
            self.activate(_test_fail_at="after")
        self.assertNotEqual(self.catalog.read_bytes(),self.initial_bytes)
        restored=self.rollback()
        self.assertEqual(restored["state"],"RESTORED_PREVIOUS_CATALOG")
        self.assertEqual(self.catalog.read_bytes(),self.initial_bytes)
        self.assertEqual(self.pointer.read_bytes(),before)


if __name__=="__main__":
    import unittest
    unittest.main()
