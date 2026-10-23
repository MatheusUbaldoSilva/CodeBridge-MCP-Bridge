"""Read-only post-update bootstrap-tool verifier contract."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from installer.rag_p9b_postupdate_mcp_tool_probe import (
    inspect_postupdate_mcp_tool, main,
)


class PostUpdateToolProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"CodeBridge"
        for rel in (
            "runtime/python/python.exe",
            "author_mcp/mcp_server.py",
            "rag/runtime/incremental_authorized_queue_bootstrap.py",
        ):
            path=self.root/rel
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(b"synthetic")
        self.gen="v1_delta_1ae1d01ea84f4e"

    def probe(self,stdout=None,code=0):
        if stdout is None:
            stdout=json.dumps({
                "state":"POSTUPDATE_MCP_TOOL_OBSERVED",
                "registered":True,"execute_default":False,
                "preview_state":"BOOTSTRAP_PLAN_ONLY",
                "public_generation":self.gen,
                "bootstrap_executed":False,"safe_to_publish":False,
                "registered_count":1,
            })
        with patch(
            "installer.rag_p9b_postupdate_mcp_tool_probe.subprocess.run",
            return_value=SimpleNamespace(returncode=code,stdout=stdout,stderr=""),
        ) as run:
            result=inspect_postupdate_mcp_tool(
                self.root, expected_generation=self.gen,
            )
        return result,run.call_args

    def test_correct_schema_is_only_observation_not_deployment(self):
        report,args=self.probe()
        self.assertTrue(report["verified"])
        self.assertEqual(report["state"],"POSTUPDATE_MCP_TOOL_READONLY_VERIFIED")
        self.assertFalse(report["deployment_authorized"])
        self.assertFalse(report["mcp_service_started"])
        self.assertFalse(report["job_queue_initialized"])
        self.assertIn("-B",args.args[0])
        self.assertEqual(args.kwargs["env"]["PYTHONDONTWRITEBYTECODE"],"1")

    def test_empty_or_malformed_expected_generation_blocks_subprocess(self):
        for generation in ("", " ", "\n", " v1 ", None, 13, "x"*129):
            with self.subTest(generation=generation):
                with patch("installer.rag_p9b_postupdate_mcp_tool_probe.subprocess.run",
                           side_effect=AssertionError("should not spawn subprocess")):
                    result=inspect_postupdate_mcp_tool(
                        self.root,expected_generation=generation)
                self.assertEqual(result["reason"],"INVALID_EXPECTED_GENERATION")
                self.assertFalse(result["verified"])

    def test_source_absent_refuses_execution(self):
        (self.root/"rag/runtime/incremental_authorized_queue_bootstrap.py").unlink()
        with patch(
            "installer.rag_p9b_postupdate_mcp_tool_probe.subprocess.run",
            side_effect=AssertionError("Do not execute"),
        ):
            report=inspect_postupdate_mcp_tool(
                self.root,expected_generation=self.gen,
            )
        self.assertEqual(report["reason"],"MCP_TOOL_SOURCE_NOT_INSTALLED")
        self.assertFalse(report["verified"])

    def test_unapproved_mutation_or_default_is_rejected(self):
        for prop in ("bootstrap_executed","safe_to_publish","execute_default"):
            with self.subTest(property=prop):
                data={
                    "state":"POSTUPDATE_MCP_TOOL_OBSERVED",
                    "registered":True,
                    "execute_default":False,
                    "preview_state":"BOOTSTRAP_PLAN_ONLY",
                    "public_generation":self.gen,
                    "bootstrap_executed":False,
                    "safe_to_publish":False,
                    "registered_count":1,
                }
                data[prop]=True
                report,_=self.probe(stdout=json.dumps(data))
                self.assertEqual(report["reason"],"MCP_TOOL_CONTRACT_UNVERIFIED")

    def test_non_object_child_json_fails_closed(self):
        for body in ("[]", "null", "true", "5", '"text"'):
            with self.subTest(body=body):
                report,_=self.probe(stdout=body)
                self.assertEqual(report["reason"],"MCP_TOOL_CONTRACT_UNVERIFIED")
                self.assertFalse(report["verified"])

    def test_unregistered_tool_must_never_pass_postupdate_gate(self):
        for value in (False, None, "true", 1):
            with self.subTest(value=value):
                data={
                    "state":"POSTUPDATE_MCP_TOOL_OBSERVED",
                    "registered":value,
                    "execute_default":False,
                    "preview_state":"BOOTSTRAP_PLAN_ONLY",
                    "public_generation":self.gen,
                    "bootstrap_executed":False,
                    "safe_to_publish":False,
                    "registered_count":1,
                }
                report,_=self.probe(stdout=json.dumps(data))
                self.assertEqual(report["reason"],"MCP_TOOL_CONTRACT_UNVERIFIED")
                self.assertFalse(report["verified"])
                self.assertFalse(report["deployment_authorized"])

    def test_changed_public_generation_is_blocked(self):
        data={
            "state":"POSTUPDATE_MCP_TOOL_OBSERVED",
            "execute_default":False,
            "preview_state":"BOOTSTRAP_PLAN_ONLY",
            "public_generation":"v1_delta_aaaaaaaaaaaaaa",
            "bootstrap_executed":False,
            "safe_to_publish":False,
            "registered_count":1,
        }
        report,_=self.probe(json.dumps(data))
        self.assertFalse(report["verified"])

    def test_wrong_child_exit_is_not_ignored(self):
        report,_=self.probe(stdout="",code=3)
        self.assertEqual(report["reason"],"MCP_TOOL_PROCESS_FAILED")

    def test_cli_rejects_missing_deployed_module_without_launching_mcp(self):
        (self.root/"rag/runtime/incremental_authorized_queue_bootstrap.py").unlink()
        with patch(
            "installer.rag_p9b_postupdate_mcp_tool_probe.subprocess.run",
            side_effect=AssertionError("must not start process"),
        ):
            self.assertEqual(main([
                "--install-root",str(self.root),
                "--generation",self.gen,
            ]),2)

    def test_nsis_installs_standalone_postupdate_probe(self):
        nsis=Path("installer/CodeBridge.nsi").read_text(encoding="utf-8")
        self.assertEqual(nsis.count(
            '  File "rag_p9b_postupdate_mcp_tool_probe.py"'),1)

    def test_invalid_timeout_and_missing_root_blocked(self):
        for timeout in (0,100,None,True):
            report=inspect_postupdate_mcp_tool(
                self.root,expected_generation=self.gen,
                timeout_seconds=timeout,
            )
            # bool is an int subclass, but not an acceptable clock interval.
            self.assertEqual(report["reason"],"INVALID_PROBE_TIMEOUT")
        self.assertFalse(inspect_postupdate_mcp_tool(
            self.root/"missing",expected_generation=self.gen,
        )["verified"])


if __name__=="__main__":
    unittest.main()
