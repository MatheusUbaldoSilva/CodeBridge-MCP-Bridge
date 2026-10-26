"""RAG-AUTO-03 MCP tool catalog and explicit consent forwarding (no live writes)."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"author_mcp"))
import mcp_server


class Auto03McpTests(unittest.TestCase):
    def test_four_new_tools_are_registered_once(self):
        names=[t.name for t in mcp_server.mcp._tool_manager.list_tools()]
        required={
            "codebridge_rag_auto_canary_status",
            "codebridge_rag_auto_prepare_candidate",
            "codebridge_rag_auto_enable_canary",
            "codebridge_rag_auto_rollback_canary",
        }
        for name in required:
            with self.subTest(name=name):
                self.assertEqual(names.count(name),1)

    def test_no_job_does_not_implicitly_prepare(self):
        result=mcp_server.codebridge_rag_auto_prepare_candidate("0"*32)
        self.assertFalse(result["operation_ok"])
        self.assertFalse(result["index_published"])
        self.assertFalse(result["public_generation_changed"])

    def test_missing_authorization_is_refused(self):
        for name,tool in (
            ("prepare",mcp_server.codebridge_rag_auto_prepare_candidate),
            ("enable",mcp_server.codebridge_rag_auto_enable_canary),
            ("rollback",mcp_server.codebridge_rag_auto_rollback_canary),
        ):
            with self.subTest(name=name):
                result=tool("0"*32)
                self.assertFalse(result["operation_ok"])
                self.assertFalse(result["worker_started"])

    def test_explicit_operations_pass_intended_confirmations(self):
        for name,wrapper,attribute,token in (
            ("prepare",mcp_server.codebridge_rag_auto_prepare_candidate,
             "prepare_auto_candidate","RAG_AUTO_PREPARE:project:"),
            ("enable",mcp_server.codebridge_rag_auto_enable_canary,
             "enable_auto_canary","RAG_AUTO_CANARY:project:"),
            ("rollback",mcp_server.codebridge_rag_auto_rollback_canary,
             "disable_auto_canary","RAG_AUTO_CANARY_ROLLBACK:"),
        ):
            with self.subTest(name=name), patch(
                "rag.runtime.auto_index_promotion."+attribute,
                return_value={"state":"CANARY_TEST","public_pointer_updated":False},
            ) as action:
                result=wrapper("a"*32,execute=True,operator_approved=True,
                               confirmation=token+"a"*32)
                self.assertTrue(result["operation_ok"])
                self.assertFalse(result["public_generation_changed"])
                action.assert_called_once()


if __name__=="__main__":
    unittest.main()
