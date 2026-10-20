import unittest
from pathlib import Path
from unittest.mock import patch

from installer.runtime_postupdate_verify import verify_installed_update

def baseline():
    return {"files": {
        "rag_manifest": {"exists": True, "sha256": "m", "bytes": 10},
        "rag_sqlite": {"exists": True, "sha256": "s", "bytes": 20},
        "rag_qdrant": {"exists": True, "sha256": "q", "bytes": 30, "file_count": 2},
    }}

class PostUpdateVerifierTests(unittest.TestCase):
    def check(self, ready, after):
        with patch("installer.runtime_postupdate_verify.inspect_embedded_runtime",
                   return_value={"ready": ready}), patch(
                   "installer.runtime_postupdate_verify.collect_runtime_fingerprints",
                   return_value=after):
            return verify_installed_update(Path("C:/install"),Path("C:/rag"),baseline())

    def test_ready_and_unchanged_is_verified_but_not_activated(self):
        result=self.check(True,baseline())
        self.assertEqual(result["state"],"POST_UPDATE_PREREQUISITES_VERIFIED")
        self.assertTrue(result["requires_isolated_real_jina_worker_test"])
        self.assertTrue(result["requires_mcp_handshake"])
        self.assertFalse(result["deployment_approved"])
        self.assertFalse(result["phase_closed"])
        self.assertTrue(result["does_not_activate_worker"])
        self.assertFalse(result["writes_performed"])

    def test_missing_qdrant_blocks_release(self):
        self.assertEqual(self.check(False,baseline())["state"],"POST_UPDATE_BLOCKED")

    def test_modified_public_sqlite_blocks_release(self):
        changed=baseline()
        changed["files"]["rag_sqlite"]["sha256"]="different"
        result=self.check(True,changed)
        self.assertEqual(result["state"],"POST_UPDATE_BLOCKED")
        self.assertFalse(result["public_index_intact"])

    def test_cli_rejects_schema_less_baseline_without_runtime_change(self):
        import json
        import subprocess
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            baseline=root/"baseline.json"
            baseline.write_text(json.dumps({"files":{
                "rag_manifest":{"exists":True,"sha256":"a"*64,"bytes":1},
                "rag_sqlite":{"exists":True,"sha256":"b"*64,"bytes":2},
                "rag_qdrant":{"exists":True,"sha256":"c"*64,"bytes":3,
                              "file_count":1},
            }}))
            command=[sys.executable,"-m","installer.runtime_postupdate_verify",
                     "--install-root",str(root/"install"),
                     "--rag-state",str(root/"rag"),
                     "--baseline-json",str(baseline)]
            run=subprocess.run(command,cwd=Path(__file__).resolve().parents[1],
                               capture_output=True,text=True,timeout=30)
            self.assertEqual(run.returncode,2,run.stderr)
            self.assertIn("POST_UPDATE_BASELINE_INVALID",run.stdout)
            self.assertFalse((root/"install").exists())
