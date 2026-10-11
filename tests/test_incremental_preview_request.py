import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag.runtime.incremental_preview_request import matching_preview_request

class PreviewRequestTests(unittest.TestCase):
    def test_valid_and_cancelled_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            request=(3,"demo",str(Path(tmp).resolve()))
            self.assertTrue(matching_preview_request(request,3,"demo",tmp))
            self.assertFalse(matching_preview_request(None,3,"demo",tmp))
            self.assertFalse(matching_preview_request(request,4,"demo",tmp))
    def test_scope_changes_invalidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            request=(1,"demo",str(Path(tmp).resolve()))
            self.assertFalse(matching_preview_request(request,1,"other",tmp))
            self.assertFalse(matching_preview_request(request,1,"demo",str(Path(tmp)/"other")))
            self.assertFalse(matching_preview_request(request,1,"demo",""))
if __name__=="__main__":
    unittest.main()
