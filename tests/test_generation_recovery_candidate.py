import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_validate import fixture
from rag.runtime.generation_recovery_candidate import (
    verify_recovery_candidate, inspect_recovery_candidates, RecoveryCandidateError,
)

class CandidateRecoveryTests(unittest.TestCase):
    def test_valid_and_invalid_without_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            base = root / "generations"
            base.mkdir(parents=True)
            good = base / "gen_good"
            bad = base / "gen_bad"
            good.mkdir()
            bad.mkdir()
            fixture(good)
            (bad / "rag_index.sqlite3").write_bytes(b"bad")
            result = verify_recovery_candidate(root, "gen_good")
            self.assertEqual(result["state"], "VALIDATED_CANDIDATE_NOT_ACTIVATED")
            self.assertEqual(result["report"]["documents"], 1)
            with self.assertRaises(RecoveryCandidateError):
                verify_recovery_candidate(root, "gen_bad")
            report = inspect_recovery_candidates(root)
            self.assertEqual([r["generation"] for r in report["validated"]], ["gen_good"])
            self.assertEqual(report["rejected"], ["gen_bad"])
            self.assertFalse(report["automatic_recovery"])
            self.assertIsNone(report["selected"])
            self.assertFalse((root / "active-generation.json").exists())

    def test_reject_traversal_and_non_test_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            with self.assertRaises(RecoveryCandidateError):
                verify_recovery_candidate(root, "../outside")
            with self.assertRaises(RecoveryCandidateError):
                inspect_recovery_candidates(tmp)

if __name__ == "__main__":
    unittest.main()
