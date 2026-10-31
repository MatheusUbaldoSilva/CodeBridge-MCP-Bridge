"""G-19: strict synthetic scratch parent rejects observed ACE risks."""
from unittest import TestCase
from unittest.mock import patch
import rag.runtime.knowledge_deletion_mac_pipe_parent_lab as parent

_SAFE=dict(state="WIN32_PIPE_ACE_INVENTORY_READ_ONLY",dacl_observed=True,
           broad_allow_ace_detected=False,unsupported_ace_detected=False,
           ace_count=3)

class ParentPipeAcePreflightTests(TestCase):
    def test_real_scratch_worker_proceeds_on_observed_native_aces(self):
        proof=parent.scratch_mac_pipe_roundtrip(entrypoint="real-worker")
        self.assertTrue(proof["mac_verified"])
        self.assertTrue(proof["parent_pipe_known_broad_aces_absent"])
        self.assertFalse(proof["secure_handle_acl_attested"])
        self.assertFalse(proof["operational_use_allowed"])
    def assert_denied(self,ace_evidence):
        spawned=[]
        original=parent.subprocess.Popen
        def tracked(*args,**kwargs):
            p=original(*args,**kwargs)
            spawned.append(p)
            return p
        with patch.object(parent,"inspect_pipe_allow_aces_read_only_dev",
                          return_value=ace_evidence),             patch.object(parent.subprocess,"Popen",side_effect=tracked):
            with self.assertRaisesRegex(RuntimeError,"scratch parent pipe ACE risk"):
                parent.scratch_mac_pipe_roundtrip()
        self.assertEqual(len(spawned),1)
        self.assertIsNotNone(spawned[0].poll())
        self.assertTrue(all(s.closed for s in (
            spawned[0].stdin,spawned[0].stdout,spawned[0].stderr)))
    def test_everyone_allow_denied(self):
        self.assert_denied(_SAFE|{"broad_allow_ace_detected":True})
    def test_unhandled_ace_denied(self):
        self.assert_denied(_SAFE|{"unsupported_ace_detected":True})
    def test_missing_dacl_denied(self):
        self.assert_denied(_SAFE|{"state":"WIN32_PIPE_ACE_INVENTORY_BLOCKED",
            "dacl_observed":False})
    def test_empty_dacl_denied(self):
        self.assert_denied(_SAFE|{"ace_count":0})
    def test_forged_ace_count_denied(self):
        self.assert_denied(_SAFE|{"ace_count":"three"})
    def test_truncated_inventory_denied(self):
        self.assert_denied(_SAFE|{"state":"WIN32_PIPE_ACE_INVENTORY_BLOCKED"})
