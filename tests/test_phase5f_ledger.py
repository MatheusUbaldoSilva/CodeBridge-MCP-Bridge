import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(r"C:\Users\Matheus\CodeBridge-MCP-Bridge")
sys.path.insert(0,str(ROOT/"app_rewrite"))
from execution_ledger import ExecutionLedger

class Phase5FTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/"ledger.db"
        self.l=ExecutionLedger(self.db)
        self.l.create("exec1","req1","POWERSHELL5.1","hash","rt")
        self.l.transition("exec1","RUNNING",runtime_instance="rt")

    def tearDown(self):
        self.tmp.cleanup()

    def test_chunk_cursor(self):
        self.l.append_output("exec1","ABC")
        self.l.append_output("exec1","DEFG")
        a=self.l.read_output("exec1",0,4)
        self.assertEqual(a["text"],"ABCD")
        self.assertEqual(a["next_cursor"],4)
        self.assertTrue(a["has_more"])
        b=self.l.read_output("exec1",4,4)
        self.assertEqual(b["text"],"EFG")
        self.assertEqual(b["next_cursor"],7)
    def test_terminal_eof(self):
        self.l.append_output("exec1","HELLO")
        self.l.transition("exec1","FINISHED",runtime_instance="rt",exit_code=0,output="HELLO")
        r=self.l.read_output("exec1",0,10)
        self.assertTrue(r["complete"])
        self.assertTrue(r["eof"])
        self.assertFalse(r["has_more"])

    def test_sync_repairs_stream(self):
        self.l.append_output("exec1","BAD")
        result=self.l.sync_output("exec1","GOOD-OUTPUT",chunk_size=1024)
        self.assertTrue(result["rewritten"])
        r=self.l.read_output("exec1",0,100)
        self.assertEqual(r["text"],"GOOD-OUTPUT")

    def test_persists_chunks_after_reopen(self):
        self.l.append_output("exec1","ONE")
        self.l.append_output("exec1","TWO")
        reopened=ExecutionLedger(self.db)
        r=reopened.read_output("exec1",0,100)
        self.assertEqual(r["text"],"ONETWO")
        self.assertEqual(r["available_chars"],6)

if __name__ == "__main__":
    unittest.main(verbosity=2)
