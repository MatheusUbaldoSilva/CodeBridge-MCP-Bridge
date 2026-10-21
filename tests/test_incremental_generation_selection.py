import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime.production_incremental_generation_selection import select_incremental_generation


class GenerationSelectionTests(unittest.TestCase):
    def test_wrong_generation_counts_never_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "v1_delta_123456789abcde"
            folder.mkdir()
            receipt = {
                "generation": folder.name,
                "status": "VERSIONED_GENERATION_VALIDATED_NOT_ACTIVE",
                "activation_permitted": False,
                "validation": {"documents": 211, "chunks": 8778, "vectors": 8778, "manifest_entries": 211},
            }
            (folder / "generation-receipt.json").write_text(json.dumps(receipt))
            result = select_incremental_generation(temp)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertIsNone(result["candidate"])

    def test_only_exact_unique_closed_receipt_matches(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "v1_delta_123456789abcde"
            folder.mkdir()
            receipt = {
                "generation": folder.name,
                "status": "VERSIONED_GENERATION_VALIDATED_NOT_ACTIVE",
                "activation_permitted": False,
                "validation": {"documents": 211, "chunks": 8763, "vectors": 8763, "manifest_entries": 211},
            }
            (folder / "generation-receipt.json").write_text(json.dumps(receipt))
            official = Path(temp) / "generations"
            official.mkdir()
            folder.rename(official / folder.name)
            with patch(
                "rag.runtime.status.resolve_rag_sqlite_path",
                return_value=Path(temp) / "rag_index.sqlite3",
            ), patch(
                "rag.runtime.production_cutover_gate._verify_versioned",
                return_value={"validation": receipt["validation"], "sha_verified": True},
            ):
                result = select_incremental_generation(official)
            self.assertEqual(result["state"], "MATCHED_NOT_AUTHORIZED")
            self.assertEqual(result["candidate"], folder.name)
            self.assertFalse(result["activation_authorized"])


if __name__ == "__main__":
    unittest.main()
