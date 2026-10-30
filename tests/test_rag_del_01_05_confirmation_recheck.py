from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from rag.runtime.knowledge_deletion_confirmation_recheck import recheck_deletion_confirmation,DeletionConfirmationStale

class ConfirmationRecheckTests(TestCase):
    def setUp(self):
        t=TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.preview={"project_id":"demo","selected_paths":["a.cpp"],
          "deletion_authorized":False,"candidate_created":False,
          "review_sha256":"a"*64,"source_revision":"b"*64}
        self.preflight={"old_catalog_sha256":"c"*64,
            "public_pointer_sha256":"d"*64,"activation_authorized":False}
        p1=patch("rag.runtime.knowledge_deletion_confirmation_recheck.preview_knowledge_removal",return_value=self.preview)
        p2=patch("rag.runtime.knowledge_deletion_confirmation_recheck.inspect_private_deletion_preflight",return_value=self.preflight)
        self.preview_fn=p1.start();self.preflight_fn=p2.start()
        self.addCleanup(p1.stop);self.addCleanup(p2.stop)
    def run_check(self):
        return recheck_deletion_confirmation("demo",["a.cpp"],"a"*64,
            "c"*64,"d"*64,{"index_family":"RAG_DEL_01"},
            catalog_file=self.root/"project-indexes.json",
            public_pointer=self.root/"public.json")
    def test_stable_selection_only_rechecks(self):
        result=self.run_check()
        self.assertFalse(result["activation_authorized"])
        self.assertTrue(result["additional_operator_confirmation_required"])
    def test_preview_revision_change_denied(self):
        self.preview["review_sha256"]="e"*64
        with self.assertRaises(DeletionConfirmationStale):self.run_check()
        self.preflight_fn.assert_not_called()
    def test_public_pointer_change_denied(self):
        self.preflight["public_pointer_sha256"]="e"*64
        with self.assertRaises(DeletionConfirmationStale):self.run_check()
    def test_catalog_change_denied(self):
        self.preflight["old_catalog_sha256"]="e"*64
        with self.assertRaises(DeletionConfirmationStale):self.run_check()
    def test_public_namespace_denied_before_lookup(self):
        with self.assertRaises(DeletionConfirmationStale):
            recheck_deletion_confirmation("codebridge",["a.cpp"],"a"*64,"c"*64,"d"*64,{},
                catalog_file=self.root/"project-indexes.json",
                public_pointer=self.root/"public.json")
        self.preview_fn.assert_not_called()
