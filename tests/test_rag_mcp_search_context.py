import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from rag.index.fts5 import initialize_fts5
from rag.index.sqlite_schema import (
    DEFAULT_DATABASE_FILENAME,
    connect_rag_index,
)


ROOT = Path(__file__).resolve().parents[1]
AUTHOR_MCP = ROOT / "author_mcp"
MCP_PYTHON = AUTHOR_MCP / ".venv" / "Scripts" / "python.exe"


class RagMcpSearchContextTests(unittest.TestCase):
    def make_local_index(self, local_app_data):
        state = Path(local_app_data) / "CodeBridge" / "rag"
        state.mkdir(parents=True)
        database = state / DEFAULT_DATABASE_FILENAME
        connection = connect_rag_index(database)
        connection.execute(
            """
            INSERT INTO rag_documents (
                document_id,
                project_id,
                source_type,
                content
            ) VALUES (
                'doc-1',
                'codebridge',
                'CODE',
                'source'
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
                git_branch
            ) VALUES (
                'chunk-1',
                'doc-1',
                'codebridge',
                0,
                'onde controla cancelamento do runtime',
                'CODE',
                'src/runtime.py',
                'main'
            )
            """
        )
        connection.commit()
        initialize_fts5(connection)
        connection.close()
        return database

    def test_tool_is_registered_and_searches_with_explicit_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            local = Path(td) / "local"
            self.make_local_index(local)

            script = r"""
import json
import mcp_server

registered = sorted(mcp_server.mcp._tool_manager._tools.keys())
result = mcp_server.codebridge_search_context(
    query="onde controla cancelamento do runtime",
    project="codebridge",
    source_types=["CODE"],
    top_k=5,
    path_filter="src/",
    branch="main",
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
                "codebridge_search_context",
                payload["registered"],
            )
            result = payload["result"]
            self.assertTrue(result["operation_ok"])
            self.assertEqual(result["requested_route"], "CODE")
            self.assertEqual(
                result["effective_route"],
                "LEXICAL_ONLY",
            )
            self.assertEqual(
                result["fallback_reason"],
                "SEMANTIC_EXECUTOR_UNAVAILABLE",
            )
            self.assertEqual(result["result_count"], 1)
            self.assertEqual(
                result["results"][0]["chunk_id"],
                "chunk-1",
            )

    def test_missing_index_returns_structured_error(self):
        with tempfile.TemporaryDirectory() as td:
            script = r"""
import json
import mcp_server

result = mcp_server.codebridge_search_context(
    query="cancelamento",
    project="codebridge",
).model_dump()
print(json.dumps(result))
"""
            env = os.environ.copy()
            env["LOCALAPPDATA"] = str(Path(td) / "missing")
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
                "INDEX_UNAVAILABLE",
            )
            self.assertEqual(result["results"], [])
            self.assertEqual(result["result_count"], 0)

    def test_registered_semantic_executor_is_used(self):
        with tempfile.TemporaryDirectory() as td:
            local = Path(td) / "local"
            self.make_local_index(local)

            script = r"""
import json
import mcp_server
import rag_bridge

def executor(query, route):
    from rag.contracts import SearchResult, SourceMetadata, SourceType
    return (
        SearchResult(
            chunk_id="semantic-1",
            document_id="doc-semantic",
            content="semantic result",
            metadata=SourceMetadata(
                project_id=query.project_id,
                source_type=SourceType.CODE,
            ),
            score=0.99,
            rank=1,
            retrieval_modes=("TEST_SEMANTIC",),
        ),
    )

rag_bridge.register_rag_search_executor(executor)

result = mcp_server.codebridge_search_context(
    query="onde controla cancelamento do runtime",
    project="codebridge",
    top_k=3,
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

            self.assertTrue(result["operation_ok"])
            self.assertEqual(result["requested_route"], "CODE")
            self.assertEqual(result["effective_route"], "CODE")
            self.assertIsNone(result["fallback_reason"])
            self.assertEqual(
                result["results"][0]["chunk_id"],
                "semantic-1",
            )


if __name__ == "__main__":
    unittest.main()
