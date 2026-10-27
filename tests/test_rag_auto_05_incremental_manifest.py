"""RAG-AUTO-05-C manifest-only chunk eligibility tests."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from rag.index.manifest import (
    IndexManifest, ManifestEntry, ManifestIndexKind, save_index_manifest,
)
from rag.runtime.auto_index_incremental_manifest import inspect_reusable_manifest_chunks
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


class ReusableChunkReceiptTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name)
        self.verified={"verified":True,"project_id":"lab-project","generation":str(self.base)}
        self.old={"sources":[
            {"path":"src/run.py","sha256":"a"*64,"index_kind":"CODE"},
            {"path":"docs/readme.md","sha256":"b"*64,"index_kind":"TEXT"},
        ]}
        self.entries=(
            ManifestEntry(project_id="lab-project",index_kind=ManifestIndexKind.CODE,
                path="src/run.py",size=5,mtime_ns=100,sha256="a"*64,
                chunk_ids=("code-id-one","code-id-two"),model_version="code-pin"),
            ManifestEntry(project_id="lab-project",index_kind=ManifestIndexKind.TEXT,
                path="docs/readme.md",size=8,mtime_ns=100,sha256="b"*64,
                chunk_ids=("text-id-one",),model_version="text-pin"),
        )
        self.save(self.entries)

    def save(self,entries):
        save_index_manifest(self.base/"rag-index-manifest.json",
                            IndexManifest(entries=tuple(entries)))

    def check(self,paths):
        return inspect_reusable_manifest_chunks(
            self.verified,self.old,paths,
            text_model_revision="text-pin",code_model_revision="code-pin",
        )

    def test_manifest_returns_chunk_ids_without_any_copy(self):
        result=self.check(["src/run.py","docs/readme.md"])
        self.assertEqual(result["candidate_vector_count"],3)
        self.assertEqual(result["candidate_chunk_ids"]["src/run.py"],
                         ["code-id-one","code-id-two"])
        self.assertFalse(result["qdrant_vectors_verified"])
        self.assertFalse(result["vector_copy_authorized"])
        self.assertFalse(result["public_pointer_updated"])

    def test_unreviewed_path_and_wrong_model_denied(self):
        with self.assertRaises(IncrementalPlanError):
            self.check(["unapproved.py"])
        with self.assertRaises(IncrementalPlanError):
            inspect_reusable_manifest_chunks(self.verified,self.old,
                ["src/run.py"],text_model_revision="text-pin",
                code_model_revision="different-pin")

    def test_source_hash_mismatch_denied(self):
        edited=ManifestEntry(project_id="lab-project",
            index_kind=ManifestIndexKind.CODE,path="src/run.py",
            size=5,mtime_ns=100,sha256="c"*64,
            chunk_ids=("code-id-one",),model_version="code-pin")
        self.save((edited,self.entries[1]))
        with self.assertRaises(IncrementalPlanError):
            self.check(["src/run.py"])

    def test_repeated_chunk_id_across_sources_denied(self):
        replacement=ManifestEntry(project_id="lab-project",
            index_kind=ManifestIndexKind.TEXT,path="docs/readme.md",
            size=8,mtime_ns=100,sha256="b"*64,
            chunk_ids=("code-id-one",),model_version="text-pin")
        self.save((self.entries[0],replacement))
        with self.assertRaises(IncrementalPlanError):
            self.check(["src/run.py","docs/readme.md"])

    def test_unverified_generation_or_missing_manifest_denied(self):
        with self.assertRaises(IncrementalPlanError):
            inspect_reusable_manifest_chunks(
                {**self.verified,"verified":False},self.old,
                ["src/run.py"],text_model_revision="text-pin",
                code_model_revision="code-pin")
        (self.base/"rag-index-manifest.json").unlink()
        with self.assertRaises(IncrementalPlanError):
            self.check(["src/run.py"])
