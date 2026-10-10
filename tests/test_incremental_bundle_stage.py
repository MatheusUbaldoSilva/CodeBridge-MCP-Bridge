import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.incremental_bundle_stage import stage_incremental_bundle, IncrementalBundleError


class BundleStageGuards(unittest.TestCase):
    def test_missing_snapshots_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(IncrementalBundleError):
                stage_incremental_bundle(root/'old', root/'new', root/'out', 'codebridge')
            self.assertFalse((root/'out').exists())

    def test_injected_failures_discard_staging(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('old', 'new'):
                folder = root / name
                (folder / 'qdrant').mkdir(parents=True)
                (folder / 'rag_index.sqlite3').write_bytes(b'fixture')
                (folder / 'rag-index-manifest.json').write_text('{}')
            original = (root / 'old' / 'rag_index.sqlite3').read_bytes()
            with patch('rag.runtime.incremental_bundle_stage.stage_incremental_sqlite', return_value={}), \
                 patch('rag.runtime.incremental_bundle_stage.stage_incremental_manifest', return_value={}), \
                 patch('rag.runtime.incremental_bundle_stage.stage_incremental_qdrant', return_value={}):
                for stage in ('sqlite', 'manifest', 'qdrant'):
                    with self.assertRaises(IncrementalBundleError):
                        stage_incremental_bundle(root/'old', root/'new', root/'out',
                                                 'codebridge', fail_after=stage)
                    self.assertFalse((root/'out').exists())
                    self.assertEqual((root/'old'/'rag_index.sqlite3').read_bytes(), original)

    def test_existing_destination_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('old', 'new', 'out'):
                (root/name).mkdir()
            with self.assertRaises(IncrementalBundleError):
                stage_incremental_bundle(root/'old', root/'new', root/'out', 'codebridge')


if __name__ == '__main__':
    unittest.main()
