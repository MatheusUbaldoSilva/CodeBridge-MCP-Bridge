"""Detect modification while preview fingerprint is being captured."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag.runtime.incremental_preview_confirmation import snapshot_preview

class PreviewDuringReadTests(unittest.TestCase):
    def test_rejects_file_modified_while_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"a.md"
            target.write_text("before",encoding="utf-8")
            original=Path.read_bytes
            def changing_read(path):
                data=original(path)
                if path == target:
                    target.write_text("after and larger",encoding="utf-8")
                return data
            with patch.object(Path,"read_bytes",changing_read):
                with self.assertRaisesRegex(ValueError,"changed during preview"):
                    snapshot_preview("demo",tmp,[{"path":"a.md"}])
    def test_stable_file_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/"a.md").write_text("stable",encoding="utf-8")
            result=snapshot_preview("demo",tmp,[{"path":"a.md"}])
            self.assertEqual(len(result["sha256"]),1)
if __name__=="__main__":
    unittest.main()
