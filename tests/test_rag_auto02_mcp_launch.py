"""RAG-AUTO-02 MCP start tool: explicit authorization and structured outcome."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"author_mcp"))
import mcp_server


class AutoMcpLaunchTests(unittest.TestCase):
    def test_start_defaults_to_refusal_without_any_launch(self):
        with patch("rag.runtime.auto_index_launch.launch_approved_auto_job") as launch:
            result=mcp_server.codebridge_rag_auto_start("a"*32)
        self.assertFalse(result["operation_ok"])
        self.assertFalse(result["worker_started"])
        launch.assert_not_called()

    def test_explicit_start_reports_started_not_completed(self):
        with patch("rag.runtime.auto_index_launch.launch_approved_auto_job",
                   return_value={"state":"PROCESS_STARTED_UNVERIFIED",
                                 "process_started":True,"pid":4123,
                                 "index_published":False}) as launch:
            result=mcp_server.codebridge_rag_auto_start(
                "a"*32,execute=True,operator_approved=True,
                confirmation="RAG_AUTO_LAUNCH:"+"a"*32,
            )
        self.assertTrue(result["operation_ok"])
        self.assertTrue(result["worker_started"])
        self.assertEqual(result["details"]["state"],"PROCESS_STARTED_UNVERIFIED")
        self.assertFalse(result["index_published"])
        launch.assert_called_once()

    def test_start_tool_is_registered_once(self):
        entries=mcp_server.mcp._tool_manager.list_tools()
        names=[item.name for item in entries]
        self.assertEqual(names.count("codebridge_rag_auto_start"),1)
        self.assertEqual(len(set(names)),len(names))


if __name__=="__main__":
    unittest.main()
