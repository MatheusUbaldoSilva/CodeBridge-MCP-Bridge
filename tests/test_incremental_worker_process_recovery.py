"""Cross-process offline queue lease tests on Windows; synthetic only."""
from tests.test_incremental_job_queue import DurableQueueTests
import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path
from rag.runtime.incremental_job_queue import inspect_job_queue

_SCRIPT = """
import json,sys
from pathlib import Path
from rag.runtime.incremental_job_queue import claim_approved_job
result=claim_approved_job(Path(sys.argv[1]),Path(sys.argv[2]),
    approved_paths=('sample.py',),now_epoch=float(sys.argv[3]),
    queue_enabled=True,lease_seconds=20)
print(json.dumps(result))
"""

class WorkerProcessRecoveryTests(DurableQueueTests):
    def process_claim(self, now=141):
        cp=subprocess.run([sys.executable,"-c",_SCRIPT,str(self.db),str(self.root),str(now)],
            cwd=str(Path(__file__).resolve().parents[1]),capture_output=True,text=True,timeout=30)
        self.assertEqual(cp.returncode,0,cp.stderr)
        return json.loads(cp.stdout)

    def test_two_independent_python_claimers(self):
        self.enqueue(queue_enabled=True,now_epoch=140)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            calls=[pool.submit(self.process_claim) for _ in range(2)]
            responses=[c.result() for c in calls]
        self.assertEqual(sorted(r["state"] for r in responses),
                         ["CLAIMED_FOR_OFFLINE_STAGING","QUEUE_EMPTY"])
        self.assertEqual(inspect_job_queue(self.db)["by_state"],{"CLAIMED":1})

    def test_crashed_worker_lease_recoverable_after_expiration(self):
        self.enqueue(queue_enabled=True,now_epoch=140)
        first=self.process_claim(141)
        self.assertEqual(first["state"],"CLAIMED_FOR_OFFLINE_STAGING")
        self.assertEqual(self.process_claim(160)["state"],"QUEUE_EMPTY")
        second=self.process_claim(162)
        self.assertEqual(second["state"],"CLAIMED_FOR_OFFLINE_STAGING")
        self.assertNotEqual(first["lease_token"],second["lease_token"])
        self.assertEqual(second["attempts"],2)
        self.assertEqual(inspect_job_queue(self.db)["by_state"],{"CLAIMED":1})
