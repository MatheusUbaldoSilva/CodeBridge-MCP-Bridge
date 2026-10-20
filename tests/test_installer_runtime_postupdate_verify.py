import unittest
from pathlib import Path
from unittest.mock import patch

from installer.runtime_postupdate_verify import verify_installed_update

def baseline():
    return {"files": {
        "rag_manifest": {"exists": True, "sha256": "m", "bytes": 10},
        "rag_sqlite": {"exists": True, "sha256": "s", "bytes": 20},
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
