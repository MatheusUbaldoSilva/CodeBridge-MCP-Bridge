import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag.runtime.incremental_preview_confirmation import snapshot_preview,revalidate_preview

class PreviewConfirmationTests(unittest.TestCase):
    def test_recheck_and_changed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/"a.md").write_text("before")
            snap=snapshot_preview("demo",folder,[{"path":"a.md"}])
            self.assertEqual(revalidate_preview(snap,"demo",folder)["state"],"PREVIEW_REVALIDATED_ONLY")
            (folder/"a.md").write_text("after")
            with self.assertRaises(ValueError):
                revalidate_preview(snap,"demo",folder)
    def test_scope_change_and_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/"a.md").write_text("test")
            snap=snapshot_preview("demo",folder,[{"path":"a.md"}])
            with self.assertRaises(ValueError):
                revalidate_preview(snap,"wrong",folder)
            with self.assertRaises(ValueError):
                revalidate_preview(snap,"demo",folder/"other")
            (folder/"a.md").unlink()
            with self.assertRaises(OSError):
                revalidate_preview(snap,"demo",folder)
    def test_outside_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/"selected"
            folder.mkdir()
            with self.assertRaises((ValueError,OSError)):
                snapshot_preview("demo",folder,[{"path":"../other.md"}])
if __name__=="__main__":
    unittest.main()
