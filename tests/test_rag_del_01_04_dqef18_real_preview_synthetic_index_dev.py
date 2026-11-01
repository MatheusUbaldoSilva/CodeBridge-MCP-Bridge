"""F18 integrate F16 with the actual RAG-DEL preview over a temp SQLite fixture.

This test invokes REAL preview function, but replaces the project resolver and
manifest with isolated synthetic fixture. No installed RAG is ever read.
"""
from __future__ import annotations

from contextlib import closing
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import sqlite3

import tests.test_rag_del_01_02_preview as preview_fixtures
from rag.runtime.knowledge_deletion_preview import (
    preview_knowledge_removal,
    KnowledgeDeletionPreviewError,
)
from rag.runtime.knowledge_deletion_preview_binding_dev import (
    review_deletion_preview_binding_dev as bind,
)

LOOKUP = "rag.runtime.knowledge_deletion_preview.resolve_isolated_project"


class F18ActualPreviewSyntheticIndexTests(TestCase):
    def setUp(self):
        # Reuse *only* the same synthetic fixture setup as the original
        # preview suite; original tests are not inherited/duplicated.
        preview_fixtures.KnowledgeDeletionPreviewTests.setUp(self)

    def _bind(self, paths, result=None, *, generation="auto_test", revision="f"*64):
        return bind(
            "demo", paths,
            preview_knowledge_removal("demo", paths) if result is None else result,
            expected_generation=generation, expected_source_revision=revision,
        )

    def test_synthetic_preview_exact_binding_positive(self):
        paths=["b.md","a.cpp"]
        preview=preview_knowledge_removal("demo", paths)
        report=self._bind(paths,preview)
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(report["state"],"F16_DEV_PREVIEW_FIELDS_COHERENT_NO_AUTHORITY")
        self.assertFalse(report["current_generation_attested"])
        self.assertFalse(report["preview_origin_authenticated"])
        self.assertFalse(report["activation_authorized"])

    def test_partial_preview_counts_bind_to_real_producer(self):
        preview=preview_knowledge_removal("demo", ["a.cpp"])
        self.assertEqual(preview["chunks_to_remove"],2)
        self.assertEqual(preview["chunks_to_preserve"],1)
        report=self._bind(["a.cpp"],preview)
        self.assertTrue(all(report["checks"].values()))
        self.assertFalse(report["operational_use_allowed"])

    def test_other_selection_does_not_bind(self):
        preview=preview_knowledge_removal("demo", ["a.cpp"])
        result=self._bind(["b.md"],preview)
        self.assertFalse(result["checks"]["exact_sorted_paths_match_selection"])

    def test_older_generation_fails_against_caller_expected(self):
        old=preview_knowledge_removal("demo",["a.cpp"])
        result=self._bind(["a.cpp"],old,generation="auto_new")
        self.assertFalse(result["checks"]["caller_expected_generation_matches"])
        self.assertFalse(result["current_generation_attested"])

    def test_older_revision_fails_against_caller_expected(self):
        old=preview_knowledge_removal("demo",["a.cpp"])
        result=self._bind(["a.cpp"],old,revision="a"*64)
        self.assertFalse(result["checks"]["caller_expected_revision_matches"])

    def test_tampered_preview_digest_fails(self):
        original=preview_knowledge_removal("demo",["a.cpp"])
        original["chunks_to_preserve"]+=1
        result=self._bind(["a.cpp"],original)
        self.assertFalse(result["checks"]["preview_digest_matches_canonical_payload"])

    def test_live_database_changed_after_preview_not_attested(self):
        # Demonstrates the LIMIT of this source-only comparison: no
        # operational TOCTOU guarantee is asserted after a SQLite mutation.
        old=preview_knowledge_removal("demo",["a.cpp"])
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("DELETE FROM rag_chunks WHERE path='b.md'")
            db.commit()
        still=self._bind(["a.cpp"],old)
        self.assertTrue(still["checks"]["preview_digest_matches_canonical_payload"])
        self.assertFalse(still["current_generation_attested"])
        self.assertIn("LIVE_MANIFEST_SQLITE_AND_QDRANT_NOT_PINNED",still["blockers"])
        with self.assertRaises(KnowledgeDeletionPreviewError):
            preview_knowledge_removal("demo",["a.cpp"])

    def test_synthetic_database_not_modified_by_preview_or_binding(self):
        before=self.db.read_bytes()
        preview=preview_knowledge_removal("demo",["a.cpp"])
        self._bind(["a.cpp"],preview)
        self.assertEqual(self.db.read_bytes(),before)

    def test_published_flag_forgery_is_rejected(self):
        preview=preview_knowledge_removal("demo",["a.cpp"])
        preview["public_pointer_updated"]=True
        with self.assertRaises(ValueError):
            self._bind(["a.cpp"],preview)

    def test_preview_does_not_approve_or_delete(self):
        preview=preview_knowledge_removal("demo",["a.cpp"])
        for key in ("operator_approved","deletion_authorized",
                    "candidate_created","public_pointer_updated",
                    "source_files_modified"):
            self.assertIs(preview[key],False)
        result=self._bind(["a.cpp"],preview)
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["ready_for_operational_pilot"])

    def test_missing_source_resolver_blocks_real_preview(self):
        with patch(LOOKUP,return_value=None):
            with self.assertRaises(KnowledgeDeletionPreviewError):
                preview_knowledge_removal("demo",["a.cpp"])
