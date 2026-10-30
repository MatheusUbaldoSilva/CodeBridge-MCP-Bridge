"""RAG-DEL: private file inventory must not fall back to a public index."""
import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app_rewrite"))
from rag_panel import _rag_operation


class PrivateListingFallbackTests(TestCase):
    @patch("rag.runtime.isolated_project_index.resolve_isolated_project", return_value=None)
    @patch("rag.runtime.status.resolve_rag_sqlite_path")
    def test_missing_private_generation_returns_empty(self,public_index,isolated):
        self.assertEqual(_rag_operation("documents",{"project":"private-test"}),[])
        public_index.assert_not_called()
        isolated.assert_called_once_with("private-test")
