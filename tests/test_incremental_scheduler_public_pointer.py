import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag.runtime.incremental_scheduler_public_pointer import inspect_public_pointer_for_scheduler


class PublicPointerDiagnosticTests(unittest.TestCase):
    def inspect(self, root):
        with patch(
            "rag.runtime.incremental_scheduler_public_pointer.resolve_rag_sqlite_path",
            return_value=root / "rag_index.sqlite3",
        ):
            return inspect_public_pointer_for_scheduler()

    def test_legacy_without_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            value = self.inspect(Path(tmp))
            self.assertEqual(value["generation"], "legacy")
            self.assertFalse(value["safe_to_schedule"])

    def test_versioned_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "active-generation.json").write_text(json.dumps(
                {"schema_version": 1, "generation": "v1_delta_1ae1d01ea84f4e"}
            ))
            result = self.inspect(root)
            self.assertEqual(result["state"], "PUBLIC_POINTER_OBSERVED")
            self.assertFalse(result["safe_to_schedule"])

    def test_pending_journal_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "production-generation-transition.json").write_text("{}")
            self.assertEqual(self.inspect(root)["state"], "PUBLIC_TRANSITION_PENDING")

    def test_invalid_pointer_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "active-generation.json").write_text("{invalid")
            self.assertEqual(self.inspect(root)["state"], "PUBLIC_POINTER_INVALID")


if __name__ == "__main__":
    unittest.main()
