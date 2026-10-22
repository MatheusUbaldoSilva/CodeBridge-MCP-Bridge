"""Ensure active V1 public indexing never bypasses promotion approval.

A registered staging executor is not permission to mutate the published V1.
The test uses a synthetic LOCALAPPDATA and never touches the installed index.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "author_mcp"))
import rag_bridge
from rag.runtime.index_request import RagIndexExecutionUnavailableError


class ActiveV1McpIndexGuardTests(unittest.TestCase):
    def test_configured_active_v1_blocks_execute_even_when_adapter_registered(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp)
            repo = local / "CodeBridge-MCP-Bridge"
            repo.mkdir()
            config = local / "CodeBridge-MCP-Bridge"
            config.mkdir(exist_ok=True)
            (config / "rag_v1_semantic.json").write_text(json.dumps({
                "enabled": True, "project_id": "codebridge",
                "repository_root": str(repo),
            }), encoding="utf-8")
            called = []
            original = rag_bridge._RAG_INDEX_EXECUTOR
            try:
                rag_bridge.register_rag_index_executor(
                    lambda plan: called.append(plan) or {"state": "DONE"},
                )
                with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}):
                    with self.assertRaises(RagIndexExecutionUnavailableError):
                        rag_bridge.index_rag(
                            project_id="codebridge", project_root=str(repo),
                            paths=["sample.py"], execute=True,
                        )
                self.assertEqual(called, [])
            finally:
                rag_bridge.register_rag_index_executor(original)

    def test_unapproved_repository_root_denied_before_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp)
            trusted = local / "CodeBridge-MCP-Bridge"
            trusted.mkdir()
            (trusted / "rag_v1_semantic.json").write_text(json.dumps({
                "enabled": True, "project_id": "codebridge",
                "repository_root": str(local / "approved"),
            }), encoding="utf-8")
            original = rag_bridge._RAG_INDEX_EXECUTOR
            try:
                rag_bridge.register_rag_index_executor(
                    lambda plan: self.fail("staging executor called"),
                )
                with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}):
                    with self.assertRaises(PermissionError):
                        rag_bridge.index_rag(
                            project_id="codebridge", project_root=str(local / "other"),
                            execute=True,
                        )
            finally:
                rag_bridge.register_rag_index_executor(original)


if __name__ == "__main__":
    unittest.main()
