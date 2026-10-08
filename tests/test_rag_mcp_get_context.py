import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from rag.index.sqlite_schema import (
    DEFAULT_DATABASE_FILENAME,
    connect_rag_index,
)


ROOT = Path(__file__).resolve().parents[1]
AUTHOR_MCP = ROOT / "author_mcp"
MCP_PYTHON = AUTHOR_MCP / ".venv" / "Scripts" / "python.exe"


class RagMcpGetContextTests(unittest.TestCase):
    def make_index(self, local):
        state = Path(local) / "CodeBridge" / "rag"
        state.mkdir(parents=True)
        database = state / DEFAULT_DATABASE_FILENAME
        connection = connect_rag_index(database)
        connection.execute(
            """
            INSERT INTO rag_documents (
                document_id, project_id, source_type, content, path
            ) VALUES (
                'doc-1', 'codebridge', 'CODE',
                'full document', 'src/main.py'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO rag_chunks (
                chunk_id, document_id, project_id, ordinal,
                content, source_type, path
            ) VALUES (
                'chunk-1', 'doc-1', 'codebridge', 0,
                'chunk content', 'CODE', 'src/main.py'
            )
            """
        )
        connection.commit()
        connection.close()

    def test_tool_is_registered_and_returns_selected_context(self):
        with tempfile.TemporaryDirectory() as td:
            local = Path(td) / "local"
            self.make_index(local)
            script = r"""
import json
import mcp_server

registered = sorted(mcp_server.mcp._tool_manager._tools.keys())
result = mcp_server.codebridge_get_context(
    project="codebridge",
    chunk_ids=["chunk-1"],
    include_document_content=True,
).model_dump()
print(json.dumps({
    "registered": registered,
    "result": result,
}))
"""
            env = os.environ.copy()
            env["LOCALAPPDATA"] = str(local)
            completed = subprocess.run(
                [str(MCP_PYTHON), "-c", script],
                cwd=str(AUTHOR_MCP),
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(completed.stdout)
            self.assertIn(
                "codebridge_get_context",
                payload["registered"],
            )
            result = payload["result"]
            self.assertTrue(result["operation_ok"])
            self.assertEqual(result["count"], 1)
            self.assertEqual(
                result["items"][0]["content"],
                "chunk content",
            )
            self.assertEqual(
                result["items"][0]["document_content"],
                "full document",
            )

    def test_cross_project_selection_is_structured_error(self):
        with tempfile.TemporaryDirectory() as td:
            local = Path(td) / "local"
            self.make_index(local)
            script = r"""
import json
import mcp_server

result = mcp_server.codebridge_get_context(
    project="drones",
    chunk_ids=["chunk-1"],
).model_dump()
print(json.dumps(result))
"""
            env = os.environ.copy()
            env["LOCALAPPDATA"] = str(local)
            completed = subprocess.run(
                [str(MCP_PYTHON), "-c", script],
                cwd=str(AUTHOR_MCP),
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            result = json.loads(completed.stdout)
            self.assertFalse(result["operation_ok"])
            self.assertEqual(
                result["error_type"],
                "RagContextSourceMissingError",
            )
            self.assertEqual(result["items"], [])


if __name__ == "__main__":
    unittest.main()
