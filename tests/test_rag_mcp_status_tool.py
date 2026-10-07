import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTHOR_MCP = ROOT / "author_mcp"
MCP_PYTHON = AUTHOR_MCP / ".venv" / "Scripts" / "python.exe"


class RagMcpStatusToolTests(unittest.TestCase):
    def test_author_mcp_venv_exists(self):
        self.assertTrue(MCP_PYTHON.is_file())

    def test_tool_is_registered_and_returns_required_status_fields(self):
        with tempfile.TemporaryDirectory() as td:
            script = r"""
import json
import mcp_server

registered = sorted(
    mcp_server.mcp._tool_manager._tools.keys()
)
result = mcp_server.codebridge_rag_status().model_dump()
print(json.dumps({
    "registered": registered,
    "result": result,
}))
"""
            env = os.environ.copy()
            env["LOCALAPPDATA"] = td
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
                "codebridge_rag_status",
                payload["registered"],
            )
            result = payload["result"]
            self.assertTrue(result["operation_ok"])
            self.assertTrue(result["available"])
            self.assertIn("state", result["index"])
            self.assertIn("text", result["models"])
            self.assertIn("code", result["models"])
            self.assertIn(
                result["models"]["text"]["runtime_state"],
                {"LOADED", "UNLOADED", "UNKNOWN"},
            )
            self.assertIn(
                result["models"]["code"]["runtime_state"],
                {"LOADED", "UNLOADED", "UNKNOWN"},
            )
            self.assertIn(
                result["models"]["text"]["execution_mode"],
                {"CPU", "GPU", "UNLOADED", "UNKNOWN"},
            )
            self.assertIn(
                result["models"]["code"]["execution_mode"],
                {"CPU", "GPU", "UNLOADED", "UNKNOWN"},
            )
            self.assertEqual(
                result["backend"]["vector"],
                "QDRANT_LOCAL",
            )

            rag_state = Path(td) / "CodeBridge" / "rag"
            self.assertFalse(
                rag_state.exists(),
                "rag_status must not create index state",
            )


if __name__ == "__main__":
    unittest.main()
