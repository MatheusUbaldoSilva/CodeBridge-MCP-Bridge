import unittest
import mcp_server


class OutputModePolicyTests(unittest.TestCase):
    def test_normal_small_is_integral(self):
        raw = "small\nresult\n"
        c = mcp_server._result_mode_contract(raw, "NORMAL", "exec_small")
        self.assertEqual(c["output_mode"], "NORMAL")
        self.assertFalse(c["compaction_applied"])
        self.assertEqual(c["stdout"], raw)
        self.assertEqual(c["stdout_chars"], len(raw))
        self.assertEqual(c["returned_stdout_chars"], len(raw))
        self.assertEqual(c["stdout_lines"], 2)

    def test_normal_large_compacts_automatically(self):
        raw = "HEAD\n" + ("x" * 13000) + "\nWARNING keep this\nTAIL\n"
        c = mcp_server._result_mode_contract(raw, "NORMAL", "exec_large")
        self.assertEqual(c["requested_output_mode"], "NORMAL")
        self.assertEqual(c["output_mode"], "COMPACT")
        self.assertTrue(c["compaction_applied"])
        self.assertLess(c["returned_stdout_chars"], c["stdout_chars"])
        self.assertIn("[CODEBRIDGE COMPACT]", c["stdout"])
        self.assertIn("execution_id=exec_large", c["stdout"])
        self.assertIn("[HEAD]", c["stdout"])
        self.assertIn("[TAIL]", c["stdout"])
        self.assertTrue(any("WARNING keep this" in item for item in c["important_sections"]))

    def test_compact_explicit_is_deterministic(self):
        raw = "alpha\nERROR deterministic\nomega\n"
        a = mcp_server._result_mode_contract(raw, "COMPACT", "exec_same")
        b = mcp_server._result_mode_contract(raw, "COMPACT", "exec_same")
        self.assertEqual(a, b)
        self.assertEqual(a["output_mode"], "COMPACT")
        self.assertTrue(a["compaction_applied"])
        self.assertIn("ERROR deterministic", a["stdout"])

    def test_compact_empty_does_not_create_synthetic_output(self):
        c = mcp_server._result_mode_contract("", "COMPACT", "exec_running")
        self.assertEqual(c["output_mode"], "COMPACT")
        self.assertFalse(c["compaction_applied"])
        self.assertEqual(c["stdout"], "")
        self.assertEqual(c["returned_stdout_chars"], 0)
        self.assertEqual(c["important_sections"], [])

    def test_raw_is_integral_even_when_large(self):
        raw = ("RAW-LINE\n" * 3000)
        c = mcp_server._result_mode_contract(raw, "RAW", "exec_raw")
        self.assertEqual(c["output_mode"], "RAW")
        self.assertFalse(c["compaction_applied"])
        self.assertEqual(c["stdout"], raw)
        self.assertEqual(c["stdout_chars"], len(raw))
        self.assertEqual(c["returned_stdout_chars"], len(raw))

    def test_compact_does_not_mutate_raw_value(self):
        raw = "BEGIN\n" + ("data\n" * 4000) + "TRACEBACK original\nEND\n"
        before = raw
        c = mcp_server._result_mode_contract(raw, "NORMAL", "exec_preserve")
        self.assertEqual(raw, before)
        self.assertEqual(c["stdout_chars"], len(before))
        self.assertTrue(any("TRACEBACK original" in item for item in c["important_sections"]))


if __name__ == "__main__":
    unittest.main()
