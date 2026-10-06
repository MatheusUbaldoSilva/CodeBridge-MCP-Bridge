import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"app_rewrite"
if str(APP) not in sys.path:
    sys.path.insert(0,str(APP))

from execution_ledger import ExecutionLedger


class OutputDeltaRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.ledger=ExecutionLedger(Path(self.temp.name)/"executions.db")

    def tearDown(self):
        self.temp.cleanup()

    def test_read_output_returns_delta_and_metadata_not_accumulated_output(self):
        eid="exec_delta"
        self.ledger.create(
            eid,"req_delta","POWERSHELL5.1","hash_delta",
            "runtime_a",failed_command="Write-Output x",
        )
        self.ledger.transition(eid,"RUNNING",runtime_instance="runtime_a")
        raw="A"*5000+"B"*5000
        self.ledger.sync_output(eid,raw)
        self.ledger.transition(
            eid,"FINISHED",runtime_instance="runtime_a",
            exit_code=0,output=raw,
        )
        result=self.ledger.read_output(eid,cursor=5000,max_chars=1024)
        self.assertEqual(result["cursor"],5000)
        self.assertEqual(result["next_cursor"],6024)
        self.assertEqual(result["text"],"B"*1024)
        self.assertEqual(result["available_chars"],10000)
        self.assertTrue(result["complete"])
        self.assertEqual(result["exit_code"],0)
        self.assertEqual(result["target"],"POWERSHELL5.1")
        self.assertNotIn("output",result)


if __name__=="__main__":
    unittest.main()