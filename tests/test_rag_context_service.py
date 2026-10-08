import tempfile
import unittest
from pathlib import Path

from rag.index.sqlite_schema import connect_rag_index
from rag.runtime.context_service import (
    RagContextInvalidScopeError,
    RagContextSourceMissingError,
    get_context,
)


class RagContextServiceTests(unittest.TestCase):
    def make_index(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "rag.sqlite3"
        connection = connect_rag_index(path)
        connection.execute(
            """
            INSERT INTO rag_documents (
                document_id,
                project_id,
                source_type,
                content,
                path
            ) VALUES (
                'doc-1',
                'codebridge',
                'CODE',
                'full document content',
                'src/main.py'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO rag_chunks (
                chunk_id,
                document_id,
                project_id,
                ordinal,
                content,
                source_type,
                path,
                line_start,
                line_end
            ) VALUES (
                'chunk-1',
                'doc-1',
                'codebridge',
                0,
                'selected chunk content',
                'CODE',
                'src/main.py',
                1,
                3
            )
            """
        )
        connection.commit()
        connection.close()
        return path

    def test_selected_chunk_is_retrieved(self):
        path = self.make_index()
        result = get_context(
            project_id="codebridge",
            chunk_ids=("chunk-1",),
            sqlite_path=path,
        )
        self.assertEqual(result.project_id, "codebridge")
        self.assertEqual(len(result.items), 1)
        item = result.items[0]
        self.assertEqual(item.content, "selected chunk content")
        self.assertEqual(item.path, "src/main.py")
        self.assertIsNone(item.document_content)

    def test_full_document_is_optional_and_authorized_by_selection(self):
        path = self.make_index()
        result = get_context(
            project_id="codebridge",
            chunk_ids=("chunk-1",),
            include_document_content=True,
            sqlite_path=path,
        )
        self.assertEqual(
            result.items[0].document_content,
            "full document content",
        )

    def test_wrong_project_cannot_read_chunk(self):
        path = self.make_index()
        with self.assertRaises(RagContextSourceMissingError):
            get_context(
                project_id="drones",
                chunk_ids=("chunk-1",),
                sqlite_path=path,
            )

    def test_missing_chunk_is_structured_error(self):
        path = self.make_index()
        with self.assertRaises(RagContextSourceMissingError):
            get_context(
                project_id="codebridge",
                chunk_ids=("missing",),
                sqlite_path=path,
            )

    def test_empty_duplicate_and_large_selection_are_rejected(self):
        path = self.make_index()
        with self.assertRaises(RagContextInvalidScopeError):
            get_context(
                project_id="codebridge",
                chunk_ids=(),
                sqlite_path=path,
            )
        with self.assertRaises(RagContextInvalidScopeError):
            get_context(
                project_id="codebridge",
                chunk_ids=("chunk-1", "chunk-1"),
                sqlite_path=path,
            )
        with self.assertRaises(RagContextInvalidScopeError):
            get_context(
                project_id="codebridge",
                chunk_ids=tuple(
                    f"chunk-{index}"
                    for index in range(101)
                ),
                sqlite_path=path,
            )


if __name__ == "__main__":
    unittest.main()
