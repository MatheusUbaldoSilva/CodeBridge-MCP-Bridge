"""RAG-AUTO-05-A: source-level incremental planning contract tests."""
from __future__ import annotations

import unittest

from rag.runtime.auto_index_incremental_plan import (
    IncrementalPlanError, compare_frozen_inventories,
)


def manifest(*rows):
    return {
        "schema_version": 1,
        "sources": [
            {"path": path, "sha256": digest, "index_kind": kind}
            for path, digest, kind in rows
        ],
    }


def plan(old, new, **override):
    values = {
        "baseline_text_model": "text-rev-1",
        "candidate_text_model": "text-rev-1",
        "baseline_code_model": "code-rev-1",
        "candidate_code_model": "code-rev-1",
    }
    values.update(override)
    return compare_frozen_inventories(old, new, **values)


class IncrementalPlanTests(unittest.TestCase):
    def test_mixed_add_change_delete_and_reuse(self):
        a, b, c = "a" * 64, "b" * 64, "c" * 64
        original = manifest(("one.py", a, "CODE"), ("two.md", b, "TEXT"),
                            ("gone.md", c, "TEXT"))
        incoming = manifest(("one.py", a, "CODE"), ("two.md", c, "TEXT"),
                            ("new.py", b, "CODE"))
        result = plan(original, incoming)
        self.assertEqual(result["eligible_reuse_sources"], ["one.py"])
        self.assertEqual(result["reindex_sources"], ["new.py", "two.md"])
        self.assertEqual(result["removed_sources"], ["gone.md"])
        self.assertEqual(result["counts"], {
            "baseline": 3, "candidate": 3, "reusable": 1,
            "reindex": 2, "removed": 1,
        })
        self.assertFalse(result["reuse_authorized"])
        self.assertFalse(result["worker_started"])
        self.assertFalse(result["public_pointer_updated"])

    def test_text_model_revision_only_reindexes_text(self):
        a = "a" * 64
        old = manifest(("src/a.py", a, "CODE"), ("docs/info.md", a, "TEXT"))
        result = plan(old, old, candidate_text_model="text-rev-2")
        self.assertEqual(result["eligible_reuse_sources"], ["src/a.py"])
        self.assertEqual(result["reindex_sources"], ["docs/info.md"])

    def test_code_model_revision_only_reindexes_code(self):
        a = "a" * 64
        old = manifest(("src/a.py", a, "CODE"), ("docs/info.md", a, "TEXT"))
        result = plan(old, old, candidate_code_model="code-rev-2")
        self.assertEqual(result["eligible_reuse_sources"], ["docs/info.md"])
        self.assertEqual(result["reindex_sources"], ["src/a.py"])

    def test_source_type_changes_force_reindex(self):
        a = "a" * 64
        result = plan(manifest(("readme", a, "TEXT")),
                      manifest(("readme", a, "CODE")))
        self.assertEqual(result["reindex_sources"], ["readme"])
        self.assertEqual(result["eligible_reuse_sources"], [])

    def test_invalid_and_duplicate_paths_fail_closed(self):
        a = "a" * 64
        good = manifest(("fine.py", a, "CODE"))
        for malicious in ("../evil", "/absolute", "a\\b", "a//b", "folder/../evil"):
            with self.subTest(path=malicious), self.assertRaises(IncrementalPlanError):
                plan(good, manifest((malicious, a, "CODE")))
        for spelling in ("C:/system", "bad" + chr(0) + "name"):
            with self.subTest(spelling=spelling), self.assertRaises(IncrementalPlanError):
                plan(good, manifest((spelling, a, "CODE")))
        with self.assertRaises(IncrementalPlanError):
            plan(good, manifest(("dup.py", a, "CODE"), ("dup.py", a, "CODE")))

    def test_invalid_digest_and_unknown_model_fail_closed(self):
        good = manifest(("fine.py", "a" * 64, "CODE"))
        with self.assertRaises(IncrementalPlanError):
            plan(good, manifest(("fine.py", "G" * 64, "CODE")))
        with self.assertRaises(IncrementalPlanError):
            plan(good, good, candidate_code_model="")

    def test_empty_candidate_or_baseline_refused(self):
        good = manifest(("fine.py", "a" * 64, "CODE"))
        with self.assertRaises(IncrementalPlanError):
            plan(good, manifest())
        with self.assertRaises(IncrementalPlanError):
            plan(manifest(), good)


if __name__ == "__main__":
    unittest.main()
