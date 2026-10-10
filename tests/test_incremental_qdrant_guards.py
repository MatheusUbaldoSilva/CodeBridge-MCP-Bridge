import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.incremental_qdrant_stage import stage_incremental_qdrant, IncrementalQdrantError

class QdrantGuardTests(unittest.TestCase):
    def test_reject_missing_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(IncrementalQdrantError):
                stage_incremental_qdrant(root/'notfound', root/'absent', root/'out', 'codebridge')
            self.assertFalse((root/'out').exists())

    def test_reject_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('old', 'new', 'out'):
                (root/name).mkdir()
            with self.assertRaises(IncrementalQdrantError):
                stage_incremental_qdrant(root/'old', root/'new', root/'out', 'codebridge')

if __name__ == '__main__':
    unittest.main()
