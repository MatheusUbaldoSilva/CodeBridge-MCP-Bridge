"""Real kernel AccessCheck tests on isolated scratch pipes; never installed GUI."""
import os
from unittest import TestCase
from unittest.mock import patch

from rag.runtime import knowledge_deletion_effective_accesscheck_dev as access


class ScratchAccessCheckTests(TestCase):
    def setUp(self):
        self.rd, self.wr = os.pipe()
        self.addCleanup(os.close, self.rd)
        self.addCleanup(os.close, self.wr)

    def test_native_accesscheck_runs_on_scratch_handle(self):
        result = access.inspect_scratch_pipe_effective_access_dev(self.rd, 0x1)
        self.assertEqual(result["state"], "SCRATCH_CURRENT_TOKEN_ACCESSCHECK_COMPLETE")
        self.assertTrue(result["access_check_completed"])
        self.assertIsInstance(result["access_granted"], bool)
        self.assertEqual(len(result["granted_mask_hex"]), 8)
        self.assertFalse(result["installed_gui_attested"])
        self.assertFalse(result["peer_token_attested"])
        self.assertFalse(result["activation_authorized"])

    def test_rejects_unbounded_or_generic_rights(self):
        for mask in (-1, 0, 0x80000000, True, 0xFFFFFFFF):
            with self.subTest(mask=mask), self.assertRaises(ValueError):
                access.inspect_scratch_pipe_effective_access_dev(self.rd, mask)

    def test_closed_descriptor_denied_without_authority(self):
        dup = os.dup(self.rd)
        os.close(dup)
        result = access.inspect_scratch_pipe_effective_access_dev(dup, 1)
        self.assertEqual(result["blockers"], ["INVALID_DESCRIPTOR"])
        self.assertFalse(result["activation_authorized"])

    def test_invalid_input_rejected(self):
        for fd in (-1, None, "1", True):
            with self.subTest(fd=fd), self.assertRaises(ValueError):
                access.inspect_scratch_pipe_effective_access_dev(fd, 1)

    def test_no_change_to_handle_inheritability(self):
        before = os.get_inheritable(self.rd)
        access.inspect_scratch_pipe_effective_access_dev(self.rd, 1)
        self.assertEqual(os.get_inheritable(self.rd), before)

    def test_null_dacl_fails_closed(self):
        with patch.object(access, "_GetSecurityInfo", return_value=0):
            result = access.inspect_scratch_pipe_effective_access_dev(self.rd, 1)
        self.assertFalse(result["access_check_completed"])
        self.assertIn("NULL_OR_ABSENT_DACL", result["blockers"])

    def test_security_query_fails_closed(self):
        with patch.object(access, "_GetSecurityInfo", return_value=5):
            result = access.inspect_scratch_pipe_effective_access_dev(self.rd, 1)
        self.assertIn("SECURITY_DESCRIPTOR_READ_FAILED", result["blockers"])
