"""RAG-DEL-01.04-A private catalog replacement read-only tests."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from rag.runtime.knowledge_deletion_catalog_plan import (
    DeletionCatalogSwapPlanError,plan_private_generation_replacement,
)


class CatalogReplacementPlanTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.catalog=root/"project-indexes.json"
        self.pointer=root/"active-generation.json"
        self.pointer.write_text(json.dumps({"schema_version":1,"generation":"stable"}))
        self.catalog.write_text(json.dumps({
            "schema_version":1,
            "projects":{"demo":{"project_id":"demo","enabled":True,
                                "source_revision":"old",
                                "generation_directory":"old-generation"},
                        "other":{"project_id":"other","enabled":True,
                                 "source_revision":"other-revision",
                                 "generation_directory":"other-generation"}},
        }))
        self.candidate={"project_id":"demo","enabled":True,
                        "source_revision":"new",
                        "generation_directory":"new-generation"}
        self.before_catalog=self.catalog.read_bytes()
        self.before_pointer=self.pointer.read_bytes()

    def plan(self):
        return plan_private_generation_replacement(
            self.catalog,self.pointer,"demo","old",self.candidate,
        )

    def test_distinct_candidate_is_only_a_plan(self):
        plan=self.plan()
        self.assertEqual(plan["project_entries_unchanged"],1)
        self.assertFalse(plan["catalog_modified"])
        self.assertFalse(plan["candidate_integrity_verified"])
        self.assertFalse(plan["activation_authorized"])
        self.assertEqual(self.before_catalog,self.catalog.read_bytes())
        self.assertEqual(self.before_pointer,self.pointer.read_bytes())

    def test_public_project_refused(self):
        with self.assertRaises(DeletionCatalogSwapPlanError):
            plan_private_generation_replacement(
                self.catalog,self.pointer,"codebridge","old",self.candidate)

    def test_wrong_revision_refused(self):
        with self.assertRaises(DeletionCatalogSwapPlanError):
            plan_private_generation_replacement(
                self.catalog,self.pointer,"demo","stale",self.candidate)

    def test_same_generation_refused(self):
        self.candidate["generation_directory"]="old-generation"
        with self.assertRaises(DeletionCatalogSwapPlanError):
            self.plan()

    def test_mismatched_project_refused(self):
        self.candidate["project_id"]="other"
        with self.assertRaises(DeletionCatalogSwapPlanError):
            self.plan()
