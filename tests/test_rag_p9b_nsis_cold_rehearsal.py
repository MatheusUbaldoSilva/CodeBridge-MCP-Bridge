"""Regression tests for full-NSIS cold rehearsal without live service restart."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from benchmarks.rag_p9b_nsis_cold_rehearsal import rehearse_cold_nsis_bootstrap


class FullNsisColdRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.repo=root/"repo"
        self.repo.mkdir()
        self.installed=root/"Programs"/"CodeBridge"
        portable=self.installed/"runtime"/"python"/"python.exe"
        portable.parent.mkdir(parents=True)
        portable.write_bytes(b"EXE test fixture")
        self.exe=root/"preview.exe"
        self.exe.write_bytes(b"MZ test fixture")
        self.snapshot=root/"snapshot.zip"
        self.snapshot.write_bytes(b"test fixture")
        self.sevenzip=root/"7z.exe"
        self.sevenzip.write_bytes(b"7Z test fixture")
        self.generation="v1_delta_1ae1d01ea84f4e"
        self.params={
            "repo":self.repo,
            "installed":self.installed,
            "installer":self.exe,
            "snapshot":self.snapshot,
            "seven_zip":self.sevenzip,
            "expected_commit":"a"*40,
            "expected_generation":self.generation,
        }
        self.targets=["author_mcp/mcp_server.py",
                      "rag/runtime/incremental_authorized_queue_bootstrap.py"]
        self.rag_output={
            "state":"STAGED_MCP_RAG_STATUS_OBSERVED",
            "operation_ok":True,
            "index_state":"READY",
            "generation":self.generation,
            "document_count":211,
            "chunk_count":8774,
        }
        self.child_output={
            "state":"POSTUPDATE_MCP_TOOL_OBSERVED",
            "registered":True,"registered_count":1,
            "execute_default":False,
            "bootstrap_executed":False,
            "safe_to_publish":False,
            "preview_state":"BOOTSTRAP_PLAN_ONLY",
            "public_generation":self.generation,
        }

    def evaluate(self, child=None, installed_baseline=True):
        calls=[]
        def child_process(argv,**kwargs):
            calls.append(argv)
            if argv[1]=="x":
                folder=next(item[2:] for item in argv if item.startswith("-o"))
                for name in self.targets:
                    target=Path(folder)/name
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_text("# temporary test",encoding="utf-8")
                return SimpleNamespace(returncode=0,stdout="",stderr="")
            return SimpleNamespace(returncode=0,
                stdout=json.dumps(child or self.child_output)
                + "\n" + json.dumps(self.rag_output), stderr="")
        with patch(
            "benchmarks.rag_p9b_nsis_cold_rehearsal.audit_p9b_nsis_payload",
            return_value={"verified":True,"sha256":"approved"},
        ), patch(
            "benchmarks.rag_p9b_nsis_cold_rehearsal.verify_installer_rollback_snapshot",
            return_value={"verified":True,"installer_sha256":"approved"},
        ), patch(
            "benchmarks.rag_p9b_nsis_cold_rehearsal.inspect_installer_snapshot_baseline",
            return_value={"matches":installed_baseline},
        ), patch(
            "benchmarks.rag_p9b_nsis_cold_rehearsal.payload_file_list",
            return_value=tuple(self.targets),
        ), patch(
            "benchmarks.rag_p9b_nsis_cold_rehearsal.subprocess.run",
            side_effect=child_process,
        ):
            result=rehearse_cold_nsis_bootstrap(**self.params)
        return result,calls

    def test_valid_staged_mcp_import_has_no_claimed_live_change(self):
        report,calls=self.evaluate()
        self.assertEqual(report["state"],"COLD_INSTALLER_READONLY_REHEARSAL_PASS")
        self.assertTrue(report["verified"])
        self.assertEqual(len(calls),2)
        self.assertIn("-B",calls[1])
        for key in (
            "installed_modified","installer_executed","queue_initialized",
            "rollback_performed","mcp_service_started",
            "live_mcp_reconnected","deployment_authorized",
        ):
            self.assertFalse(report[key],key)
        self.assertFalse((self.installed/"author_mcp"/"mcp_server.py").exists())

    def test_mutating_preview_is_refused(self):
        bad=dict(self.child_output,bootstrap_executed=True)
        report,_=self.evaluate(child=bad)
        self.assertEqual(report["reason"],"STAGED_MCP_PREVIEW_UNEXPECTED")
        self.assertFalse(report["verified"])

    def test_staged_public_rag_wrong_chunk_count_is_blocked(self):
        self.rag_output["chunk_count"]=8775
        report,_=self.evaluate()
        self.assertEqual(report["reason"],"STAGED_PUBLIC_RAG_STATUS_UNVERIFIED")
        self.assertFalse(report["verified"])

    def test_staged_public_rag_operation_failure_is_blocked(self):
        self.rag_output["operation_ok"]=False
        report,_=self.evaluate()
        self.assertEqual(report["reason"],"STAGED_PUBLIC_RAG_STATUS_UNVERIFIED")

    def test_wrong_public_generation_is_refused(self):
        bad=dict(self.child_output,public_generation="v1_delta_aaaaaaaaaaaaaa")
        report,_=self.evaluate(child=bad)
        self.assertEqual(report["reason"],"STAGED_MCP_PREVIEW_UNEXPECTED")

    def test_installed_changes_prevent_staging(self):
        report,calls=self.evaluate(installed_baseline=False)
        self.assertEqual(report["reason"],"PREUPDATE_BASELINE_CHANGED")
        self.assertEqual(calls,[])

    def test_missing_portable_runtime_denies_before_any_subprocess(self):
        (self.installed/"runtime"/"python"/"python.exe").unlink()
        report=rehearse_cold_nsis_bootstrap(**self.params)
        self.assertEqual(report["reason"],"PREREQUISITES_UNVERIFIED")

    def test_snapshot_identity_failure_does_not_extract(self):
        with patch(
            "benchmarks.rag_p9b_nsis_cold_rehearsal.audit_p9b_nsis_payload",
            return_value={"verified":True,"sha256":"good"},
        ), patch(
            "benchmarks.rag_p9b_nsis_cold_rehearsal.verify_installer_rollback_snapshot",
            return_value={"verified":True,"installer_sha256":"other"},
        ), patch(
            "benchmarks.rag_p9b_nsis_cold_rehearsal.subprocess.run",
            side_effect=AssertionError("must never extract"),
        ):
            report=rehearse_cold_nsis_bootstrap(**self.params)
        self.assertEqual(report["reason"],"BACKUP_IDENTITY_MISMATCH")


if __name__=="__main__":
    unittest.main()
