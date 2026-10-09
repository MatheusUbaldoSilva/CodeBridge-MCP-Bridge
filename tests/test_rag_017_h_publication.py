"""RAG-017-H publishing fail-closed contract and restart evidence."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rag.runtime.production_publish import RagPublicationError,publish_staged_index,validate_staged_index
from rag.runtime.status import build_rag_status

class PublicationGuards(unittest.TestCase):
    def test_incomplete_staging_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(RagPublicationError):
                validate_staged_index(td,"demo")
    def test_existing_production_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            db=root/"rag_index.sqlite3"
            db.write_bytes(b"untouched")
            with patch("rag.runtime.production_publish.validate_staged_index",return_value={"documents":1,"chunks":1,"text_vectors":1,"code_vectors":0}):
                with patch("rag.runtime.production_publish.resolve_rag_sqlite_path",return_value=db), patch("rag.runtime.production_publish.resolve_qdrant_local_path",return_value=root/"qdrant"), patch("rag.runtime.production_publish.resolve_rag_manifest_path",return_value=root/"manifest.json"):
                    with self.assertRaises(RagPublicationError):
                        publish_staged_index(td,"demo",td)
            self.assertEqual(db.read_bytes(),b"untouched")
    def test_incomplete_index_never_marked_ready(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            state=build_rag_status(local_app_data=root)
            self.assertEqual(state.index["state"],"EMPTY")

if __name__=="__main__":unittest.main()
