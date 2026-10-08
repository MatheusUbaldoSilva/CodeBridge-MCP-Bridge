import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTHOR_MCP = ROOT / "author_mcp"
MCP_PYTHON = AUTHOR_MCP / ".venv" / "Scripts" / "python.exe"


class RagMcpIndexToolTests(unittest.TestCase):
    def test_tool_is_registered_and_defaults_to_plan_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "project"
            root.mkdir()
            (root / "README.md").write_text("# Test\n", encoding="utf-8")
            (root / "main.py").write_text("print('x')\n", encoding="utf-8")

            script = r"""
import json
import sys
from pathlib import Path

project = sys.argv[1]
import mcp_server

registered = sorted(mcp_server.mcp._tool_manager._tools.keys())
result = mcp_server.codebridge_rag_index(
    project_id="codebridge",
    project_root=project,
).model_dump()

print(json.dumps({
    "registered": registered,
    "result": result,
}))
"""
            env = os.environ.copy()
            env["LOCALAPPDATA"] = str(Path(td) / "localappdata")
            completed = subprocess.run(
                [str(MCP_PYTHON), "-c", script, str(root)],
                cwd=str(AUTHOR_MCP),
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(completed.stdout)

            self.assertIn(
                "codebridge_rag_index",
                payload["registered"],
            )
            result = payload["result"]
            self.assertTrue(result["operation_ok"])
            self.assertEqual(result["action"], "PLAN")
            self.assertFalse(result["executed"])
            self.assertEqual(result["plan"]["candidate_count"], 2)
            self.assertIsNone(result["execution"])

            rag_state = (
                Path(env["LOCALAPPDATA"])
                / "CodeBridge"
                / "rag"
            )
            self.assertFalse(
                rag_state.exists(),
                "planning must not create RAG state",
            )

    def test_execute_true_without_executor_is_structured_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "project"
            root.mkdir()
            (root / "README.md").write_text("# Test\n", encoding="utf-8")

            script = r"""
import json
import sys
import mcp_server

result = mcp_server.codebridge_rag_index(
    project_id="codebridge",
    project_root=sys.argv[1],
    execute=True,
).model_dump()
print(json.dumps(result))
"""
            completed = subprocess.run(
                [str(MCP_PYTHON), "-c", script, str(root)],
                cwd=str(AUTHOR_MCP),
                capture_output=True,
                text=True,
                check=True,
            )
            result = json.loads(completed.stdout)

            self.assertFalse(result["operation_ok"])
            self.assertFalse(result["executed"])
            self.assertEqual(result["action"], "EXECUTE")
            self.assertEqual(
                result["error_type"],
                "EXECUTOR_UNAVAILABLE",
            )

    def test_explicit_execute_invokes_registered_executor_once(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "project"
            root.mkdir()
            (root / "README.md").write_text("# Test\n", encoding="utf-8")

            script = r"""
import json
import sys
import mcp_server
import rag_bridge

calls = []

def executor(plan):
    calls.append(plan.project_id)
    return {
        "status": "DONE",
        "indexed_files": plan.candidate_count,
    }

rag_bridge.register_rag_index_executor(executor)

result = mcp_server.codebridge_rag_index(
    project_id="codebridge",
    project_root=sys.argv[1],
    execute=True,
).model_dump()

print(json.dumps({
    "calls": calls,
    "result": result,
}))
"""
            completed = subprocess.run(
                [str(MCP_PYTHON), "-c", script, str(root)],
                cwd=str(AUTHOR_MCP),
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(completed.stdout)

            self.assertEqual(payload["calls"], ["codebridge"])
            result = payload["result"]
            self.assertTrue(result["operation_ok"])
            self.assertTrue(result["executed"])
            self.assertEqual(result["action"], "EXECUTE")
            self.assertEqual(result["execution"]["status"], "DONE")
            self.assertEqual(result["execution"]["indexed_files"], 1)


if __name__ == "__main__":
    unittest.main()
