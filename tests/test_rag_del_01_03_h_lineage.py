from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from rag.index.manifest import IndexManifest,ManifestEntry,ManifestIndexKind,save_index_manifest
from rag.runtime.knowledge_deletion_lineage import verify_survivor_lineage,DeletionLineageError

class DeletionLineageTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.baseline=self.root/"baseline.json"
        self.candidate=self.root/"candidate.json"
        self.rows=[ManifestEntry(project_id="demo",index_kind=ManifestIndexKind.CODE,
                 path=p+".cpp",size=1,mtime_ns=1,sha256="a"*64,
                 chunk_ids=(p+"1",p+"2"),model_version="lab") for p in ("a","b","c")]
        save_index_manifest(self.baseline,IndexManifest(tuple(self.rows)))
        save_index_manifest(self.candidate,IndexManifest(tuple(self.rows[1:])))
        self.preview={"mode":"READ_ONLY_REMOVAL_PREVIEW","project_id":"demo",
            "deletion_authorized":False,"selected_paths":["a.cpp"],
            "documents_to_remove":1,"chunks_to_remove":2,
            "documents_to_preserve":2,"chunks_to_preserve":4,
            "generation":"auto_old","source_revision":"a"*64,
            "review_sha256":"b"*64}
    def run_check(self):
        return verify_survivor_lineage(self.baseline,self.candidate,self.preview)
    def test_exact_survivors(self):
        first=self.run_check()
        self.assertEqual(first,self.run_check())
        self.assertFalse(first["activation_authorized"])
        self.assertEqual(first["preserved_chunks"],4)
    def test_unselected_file_missing_rejected(self):
        save_index_manifest(self.candidate,IndexManifest((self.rows[1],)))
        with self.assertRaises(DeletionLineageError): self.run_check()
    def test_selected_file_remaining_rejected(self):
        save_index_manifest(self.candidate,IndexManifest(tuple(self.rows)))
        with self.assertRaises(DeletionLineageError): self.run_check()
    def test_changed_sha_rejected(self):
        changed=ManifestEntry(project_id="demo",index_kind=ManifestIndexKind.CODE,
                 path="b.cpp",size=1,mtime_ns=1,sha256="c"*64,
                 chunk_ids=("b1","b2"),model_version="lab")
        save_index_manifest(self.candidate,IndexManifest((changed,self.rows[2])))
        with self.assertRaises(DeletionLineageError): self.run_check()
    def test_chunk_drift_rejected(self):
        changed=ManifestEntry(project_id="demo",index_kind=ManifestIndexKind.CODE,
                 path="b.cpp",size=1,mtime_ns=1,sha256="a"*64,
                 chunk_ids=("b1",),model_version="lab")
        save_index_manifest(self.candidate,IndexManifest((changed,self.rows[2])))
        with self.assertRaises(DeletionLineageError): self.run_check()
    def test_count_mismatch_rejected(self):
        self.preview["chunks_to_preserve"]=5
        with self.assertRaises(DeletionLineageError): self.run_check()
    def test_combined_gate_rejects_vector_count_drift(self):
        from unittest.mock import patch, Mock
        from rag.runtime.knowledge_deletion_audit_gate import audit_private_removal_candidate
        save_index_manifest(self.root/"rag-index-manifest.json",IndexManifest(tuple(self.rows[1:])))
        with patch("rag.runtime.knowledge_deletion_audit_gate.verify_candidate_vector_semantics",
                   return_value={"vectors_verified":3,"documents_verified":2}):
            with self.assertRaises(ValueError):
                audit_private_removal_candidate(
                    self.baseline,self.root,"demo",self.preview,Mock()
                )

    def test_public_project_denied(self):
        self.preview["project_id"]="codebridge"
        with self.assertRaises(DeletionLineageError): self.run_check()
