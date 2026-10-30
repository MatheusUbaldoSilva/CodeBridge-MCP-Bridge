from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from types import SimpleNamespace
from rag.index.manifest import IndexManifest,ManifestEntry,ManifestIndexKind,save_index_manifest
from rag.runtime.knowledge_deletion_vectors import plan_surviving_vector_batches
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


class SurvivorReceiptTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/"manifest.json"
        entries=tuple(ManifestEntry(project_id="demo",index_kind=ManifestIndexKind.CODE,
             path=name+".cpp",size=1,mtime_ns=1,sha256="a"*64,
             chunk_ids=tuple(name+str(i) for i in range(count)),model_version="test")
             for name,count in (("a",2),("b",3),("c",4)))
        save_index_manifest(self.path,IndexManifest(entries))
        self.preview={"generation":"auto_lab","mode":"READ_ONLY_REMOVAL_PREVIEW","deletion_authorized":False,
            "candidate_created":False,"project_id":"demo","selected_paths":["a.cpp"],
            "documents_to_preserve":2,"chunks_to_preserve":7,
            "source_revision":"f"*64,"review_sha256":"b"*64}
        p=patch("rag.runtime.knowledge_deletion_vectors.preview_knowledge_removal",side_effect=lambda project,paths:dict(self.preview))
        p.start()
        self.addCleanup(p.stop)
        p2=patch("rag.runtime.knowledge_deletion_vectors.resolve_isolated_project",return_value=SimpleNamespace(manifest=self.path))
        p2.start()
        self.addCleanup(p2.stop)

    def test_only_survivors_in_bounded_batches(self):
        result=plan_surviving_vector_batches(self.path,self.preview,max_vectors=3)
        self.assertEqual(result["vectors_to_preserve"],7)
        self.assertEqual([b["candidate_vector_count"] for b in result["batches"]],[3,3,1])
        self.assertEqual(set(result["sources"]["sources"][0]),{"path","sha256","index_kind"})
        self.assertFalse(result["vectors_copied"])
        self.assertFalse(result["activation_authorized"])
        self.assertNotIn("a.cpp",{p for b in result["batches"] for p in b["candidate_chunk_ids"]})

    def test_stale_chunk_count_fails_closed(self):
        self.preview["chunks_to_preserve"]=8
        with self.assertRaises(IncrementalPlanError):
            plan_surviving_vector_batches(self.path,self.preview)

    def test_public_namespace_fails_closed(self):
        self.preview["project_id"]="codebridge"
        with self.assertRaises(IncrementalPlanError):
            plan_surviving_vector_batches(self.path,self.preview)

    def test_unsorted_or_duplicate_selection_fails_closed(self):
        for paths in (["a.cpp","a.cpp"],["c.cpp","a.cpp"],[]):
            self.preview["selected_paths"]=paths
            with self.assertRaises(IncrementalPlanError):
                plan_surviving_vector_batches(self.path,self.preview)

    def test_missing_manifest(self):
        self.path.unlink()
        with self.assertRaises(IncrementalPlanError):
            plan_surviving_vector_batches(self.path,self.preview)
