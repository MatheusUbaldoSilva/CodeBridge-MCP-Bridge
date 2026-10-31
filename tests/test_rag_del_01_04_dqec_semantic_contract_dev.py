"""DQ-E-C prevents source-only semantic lock claims from becoming approval."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from rag.runtime.knowledge_deletion_dqec_semantic_contract_dev import (
    audit_semantic_child_pin_contract_dev,
)


class RealPrivateSemanticGateTests(TestCase):
    def test_real_dev_semantic_subprocess_is_not_fully_pinned(self):
        row=audit_semantic_child_pin_contract_dev(Path(__file__).resolve().parents[1])
        self.assertTrue(row["parent_internal_semantic_lock"])
        self.assertTrue(row["child_re_resolves_catalog"])
        self.assertFalse(row["child_accepts_explicit_pinned_manifest"])
        self.assertEqual(row["state"],"DQEC_REAL_SEMANTIC_PIN_REFACTOR_PENDING")
        self.assertFalse(row["safe_to_activate"])

    def test_missing_worker_source_never_authorizes(self):
        with TemporaryDirectory() as td:
            row=audit_semantic_child_pin_contract_dev(Path(td))
        self.assertEqual(row["state"],"DQEC_SOURCE_MISSING_OR_INVALID")
        self.assertFalse(row["safe_to_activate"])

    def test_refactored_source_static_signal_still_requires_runtime_attestation(self):
        with TemporaryDirectory() as td:
            root=Path(td)/"rag"/"runtime"
            root.mkdir(parents=True)
            (root/"isolated_project_search.py").write_text(
                "def semantic_isolated_project(query, route):\n"
                "    return run_semantic_already_locked(query, route)\n",
                encoding="utf-8",
            )
            (root/"isolated_project_worker.py").write_text(
                "def main():\n"
                "    expected = request['pinned_manifest_sha256']\n"
                "    return verify_pinned_worker_manifest(expected)\n",
                encoding="utf-8",
            )
            row=audit_semantic_child_pin_contract_dev(Path(td))
        self.assertFalse(row["parent_internal_semantic_lock"])
        self.assertFalse(row["child_re_resolves_catalog"])
        self.assertTrue(row["child_accepts_explicit_pinned_manifest"])
        self.assertEqual(row["state"],"DQEC_SOURCE_IMPROVED_RUNTIME_ATTESTATION_PENDING")
        self.assertFalse(row["operational_use_allowed"])