"""RAG-AUTO-02.5 bounded operator-started loop tests."""
from pathlib import Path
import tempfile
import unittest

from rag.runtime.auto_index_queue import create_draft,default_queue_path
from rag.runtime.auto_index_approval import build_auto_index_preview,approve_auto_index_draft
from rag.runtime.auto_index_runner import run_approved_auto_job


class AutoRunnerTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/"code"
        self.root.mkdir()
        (self.root/"a.py").write_text("print(1)\n",encoding="utf-8")
        self.db=default_queue_path(Path(tmp.name))
        draft=create_draft(
            self.db,project_id="runner-demo",source_root=self.root,
            idempotency_key="runner-test-12345678",allow_write=True,
        )
        self.job=draft["job_id"]
        preview=build_auto_index_preview("runner-demo",self.root)
        approve_auto_index_draft(
            self.db,self.job,preview,confirmed_digest=preview["review_sha256"],
            operator_approved=True,allow_write=True,
        )

    def run_loop(self,fake,**kwargs):
        settings={
            "execute":True,"operator_approved":True,
            "confirmation":"RAG_AUTO_RUN:"+self.job,
            "run_batch":fake,"max_batches":8,
        }
        settings.update(kwargs)
        return run_approved_auto_job(self.db,self.job,**settings)

    def test_no_implicit_start(self):
        called=[]
        with self.assertRaises(PermissionError):
            self.run_loop(lambda *a,**k: called.append(1),execute=False)
        self.assertEqual(called,[])

    def test_exits_after_ready(self):
        seen=[]
        def fake(*args,**kwargs):
            seen.append(kwargs)
            return {"state":"READY_FOR_REVIEW" if len(seen)==3 else "QUEUED",
                    "vectors_done":len(seen),"vectors_expected":3}
        result=self.run_loop(fake)
        self.assertEqual(result["state"],"READY_FOR_REVIEW")
        self.assertEqual(result["batches"],3)
        self.assertFalse(result["index_published"])

    def test_finite_limit(self):
        count=[]
        def fake(*args,**kwargs):
            count.append(1)
            return {"state":"QUEUED","vectors_done":len(count)}
        result=self.run_loop(fake,max_batches=2)
        self.assertEqual(result["run_ended"],"BOUNDED_LIMIT_REACHED")
        self.assertEqual(len(count),2)

    def test_low_memory_terminates(self):
        answer=self.run_loop(lambda *a,**kw:{
            "state":"WAITING_FOR_MEMORY","worker_started":False
        })
        self.assertEqual(answer["state"],"WAITING_FOR_MEMORY")
        self.assertEqual(answer["batches"],1)

    def test_rejects_invalid_batch_bounds(self):
        with self.assertRaises(ValueError):
            self.run_loop(lambda *a,**k:None,batch_size=257)
        with self.assertRaises(ValueError):
            self.run_loop(lambda *a,**k:None,max_batches=0)


if __name__=="__main__":
    unittest.main()
