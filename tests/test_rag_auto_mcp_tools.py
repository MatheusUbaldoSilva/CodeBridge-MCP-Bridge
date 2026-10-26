"""RAG-AUTO-01.8 MCP tools: proof of read-only defaults and explicit gates."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"author_mcp"))
import mcp_server
from rag.runtime import auto_index_api
from rag.runtime.auto_index_queue import get_job,inspect_queue


class AutoIndexMcpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.project="auto-mcp-test"
        self.root=self.base/"source"
        self.root.mkdir()
        (self.root/"README.md").write_text("CodeBridge test RAG\n",encoding="utf-8")
        self.db=self.base/"auto"/"jobs"/"auto_index_jobs.sqlite3"
        patcher=patch.object(auto_index_api,"default_queue_path",return_value=self.db)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_default_status_no_database_creation(self):
        response=mcp_server.codebridge_rag_auto_status()
        self.assertTrue(response["operation_ok"],response)
        self.assertEqual(response["details"]["queue"]["state"],"NOT_INITIALIZED")
        self.assertFalse(self.db.exists())

    def test_preview_readonly_and_denies_implicit_approval(self):
        preview=mcp_server.codebridge_rag_auto_preview(
            project_id=self.project,source_root=str(self.root),
        )
        self.assertTrue(preview["operation_ok"],preview)
        sha=preview["details"]["review_sha256"]
        denied=mcp_server.codebridge_rag_auto_approve(
            self.project,str(self.root),sha,
        )
        self.assertFalse(denied["operation_ok"])
        self.assertFalse(self.db.exists())
        self.assertFalse(denied["worker_started"])
        self.assertFalse(denied["index_published"])

    def test_explicit_approval_and_control(self):
        preview=mcp_server.codebridge_rag_auto_preview(
            project_id=self.project,source_root=str(self.root),
        )
        sha=preview["details"]["review_sha256"]
        reply=mcp_server.codebridge_rag_auto_approve(
            self.project,str(self.root),sha,execute=True,
            operator_approved=True,
            confirmation=f"RAG_AUTO_QUEUE:{self.project}:{sha}",
        )
        self.assertTrue(reply["operation_ok"],reply)
        self.assertEqual(reply["details"]["state"],"QUEUED")
        job=reply["details"]["job_id"]
        summary=mcp_server.codebridge_rag_auto_status(project_id=self.project)
        self.assertTrue(summary["operation_ok"])
        self.assertEqual(len(summary["details"]["jobs"]),1)
        denied=mcp_server.codebridge_rag_auto_control(job,"PAUSE")
        self.assertFalse(denied["operation_ok"])
        self.assertEqual(get_job(self.db,job)["state"],"QUEUED")
        accepted=mcp_server.codebridge_rag_auto_control(
            job,"PAUSE",execute=True,operator_approved=True,
            confirmation="RAG_AUTO_CONTROL:"+job+":PAUSE",
        )
        self.assertTrue(accepted["operation_ok"],accepted)
        self.assertEqual(accepted["details"]["state"],"PAUSED")
        self.assertFalse(accepted["worker_started"])
        self.assertFalse(accepted["public_generation_changed"])

    def test_file_change_between_preview_and_consent_denied(self):
        preview=mcp_server.codebridge_rag_auto_preview(
            project_id=self.project,source_root=str(self.root),
        )
        sha=preview["details"]["review_sha256"]
        (self.root/"README.md").write_text("Changed\n",encoding="utf-8")
        result=mcp_server.codebridge_rag_auto_approve(
            self.project,str(self.root),sha,execute=True,
            operator_approved=True,
            confirmation=f"RAG_AUTO_QUEUE:{self.project}:{sha}",
        )
        self.assertFalse(result["operation_ok"])
        self.assertFalse(self.db.exists())

    def test_idempotent_duplicate_consent(self):
        preview=mcp_server.codebridge_rag_auto_preview(
            project_id=self.project,source_root=str(self.root),
        )
        sha=preview["details"]["review_sha256"]
        opts=dict(
            project_id=self.project,source_root=str(self.root),
            confirmed_digest=sha,execute=True,operator_approved=True,
            confirmation=f"RAG_AUTO_QUEUE:{self.project}:{sha}",
        )
        a=mcp_server.codebridge_rag_auto_approve(**opts)
        b=mcp_server.codebridge_rag_auto_approve(**opts)
        self.assertTrue(a["operation_ok"])
        self.assertTrue(b["operation_ok"])
        self.assertEqual(a["details"]["job_id"],b["details"]["job_id"])
        self.assertTrue(b["details"]["reused"])
        self.assertEqual(inspect_queue(self.db)["jobs"],1)


if __name__=="__main__":
    unittest.main()
