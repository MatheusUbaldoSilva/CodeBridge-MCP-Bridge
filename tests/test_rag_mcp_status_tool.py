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

    def test_generation_probe_is_registered_and_fails_closed_without_index(self):
        with tempfile.TemporaryDirectory() as td:
            script = r"""
import json
import mcp_server
registered = "codebridge_rag_generation_probe" in (
    mcp_server.mcp._tool_manager._tools
)
result = mcp_server.codebridge_rag_generation_probe().model_dump()
print(json.dumps({
    "registered": registered,
    "state": result["state"],
    "safe_to_activate": result["safe_to_activate"],
    "operation_ok": result["operation_ok"],
}))
"""
            env = os.environ.copy()
            env["LOCALAPPDATA"] = td
            completed = subprocess.run(
                [str(MCP_PYTHON), "-c", script],
                cwd=str(AUTHOR_MCP), env=env,
                capture_output=True, text=True, check=True,
            )
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["registered"])
            self.assertEqual(payload["state"], "PUBLIC_READER_PROBE_BLOCKED")
            self.assertFalse(payload["safe_to_activate"])
            self.assertFalse(payload["operation_ok"])
            self.assertFalse((Path(td) / "CodeBridge" / "rag").exists())

    def test_semantic_worker_probe_inspects_currently_loaded_bytecode(self):
        # This checks the actual callable loaded by the MCP package;
        # a changed file on disk alone does not make the probe pass.
        script = r"""
import json
import rag_bridge
code = rag_bridge._v1_semantic_process_executor.__code__
loaded = ("production_generation_lock" in code.co_names
          and "semantic" in code.co_consts
          and "V1 semantic worker queue timed out" in code.co_consts)
print(json.dumps({"semantic_worker_serialization_loaded": loaded}))
"""
        completed = subprocess.run(
            [str(MCP_PYTHON), "-c", script],
            cwd=str(AUTHOR_MCP), capture_output=True, text=True, check=True,
        )
        result = json.loads(completed.stdout)
        self.assertTrue(result["semantic_worker_serialization_loaded"])

    def test_public_readiness_cli_fails_closed_for_old_semantic_executor(self):
        script = r"""
import asyncio,json
from unittest.mock import patch
import v1_public_readiness as readiness
async def stub(name, args):
    if name != "codebridge_rag_generation_probe":
        raise AssertionError("blocked readiness must not trigger other tools")
    return {
        "operation_ok": True, "state": "PUBLIC_READER_PROBE_PASS",
        "details": {
            "mcp_pid": 9724, "generation": "legacy",
            "loaded_reader_functions": {"search": True, "context": True, "status": True},
            "writer_blocked_during_read": True,
            "semantic_worker_serialization_loaded": False,
        },
    }
with patch.object(readiness, "_call", side_effect=stub):
    result = asyncio.run(readiness._audit(concurrent=True))
print(json.dumps(result))
"""
        result = subprocess.run(
            [str(MCP_PYTHON), "-c", script],
            cwd=str(AUTHOR_MCP), capture_output=True, text=True, check=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["state"], "BLOCKED")
        self.assertFalse(payload["safe_to_activate"])
        self.assertNotIn("hybrid_concurrent", payload)

    def test_public_readiness_cli_requires_three_valid_hybrid_results(self):
        script = r"""
import asyncio,json
from unittest.mock import patch
import v1_public_readiness as readiness
async def stub(name, args):
    if name == "codebridge_rag_generation_probe":
        return {
            "operation_ok": True, "state": "PUBLIC_READER_PROBE_PASS",
            "details": {
                "mcp_pid": 100, "generation": "legacy",
                "loaded_reader_functions": {"search": True, "context": True, "status": True},
                "writer_blocked_during_read": True,
                "semantic_worker_serialization_loaded": True,
            },
        }
    if name == "codebridge_rag_status":
        return {"index": {"state": "READY", "generation": "legacy"},
                "projects": [{"document_count": 210, "chunk_count": 8761}]}
    if name == "codebridge_search_context":
        return {"operation_ok": True, "effective_route": "HYBRID",
                "fallback_reason": None, "result_count": 3}
    raise AssertionError("unknown tool")
with patch.object(readiness, "_call", side_effect=stub):
    result = asyncio.run(readiness._audit(concurrent=True))
print(json.dumps(result))
"""
        result = subprocess.run(
            [str(MCP_PYTHON), "-c", script],
            cwd=str(AUTHOR_MCP), capture_output=True, text=True, check=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["state"], "PUBLIC_HYBRID_CONCURRENCY_PASS")
        self.assertFalse(payload["safe_to_activate"])
        self.assertEqual(len(payload["hybrid_concurrent"]), 3)
        self.assertTrue(all(item["ok"] for item in payload["hybrid_concurrent"]))

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
