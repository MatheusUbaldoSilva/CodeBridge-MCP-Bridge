"""Independent process real Jina worker staging and persisted restart evidence."""
from __future__ import annotations
from tests.test_incremental_job_queue import DurableQueueTests
from rag.runtime.incremental_job_queue import inspect_job_queue, inspect_job
from rag.models.code_artifact_install import resolve_selected_code_model_path
import json
import subprocess
import sys
from pathlib import Path

_CHILD = """
from pathlib import Path
from unittest.mock import patch
import json,sys
from rag.runtime import production_index
from rag.runtime.incremental_offline_worker import process_offline_job_once
db,project,scratch=(Path(s) for s in sys.argv[1:4])
with patch.object(production_index,'resolve_rag_sqlite_path',
                  return_value=scratch/'rag_index.sqlite3'):
    result=process_offline_job_once(db,project,approved_paths=('sample.py',),
       queue_enabled=True,worker_enabled=True)
print(json.dumps(result,sort_keys=True))
"""
_READ = """
from pathlib import Path
from rag.runtime.incremental_job_queue import inspect_job
import sys,json
print(json.dumps(inspect_job(Path(sys.argv[1]),sys.argv[2]),sort_keys=True))
"""

class IndependentWorkerRestartTests(DurableQueueTests):
    def test_real_worker_subprocess_and_new_reader(self):
        exe=Path(r"C:\llama\llama-server.exe")
        if not exe.is_file() or not resolve_selected_code_model_path().is_file():
            self.skipTest("Jina Code artifact unavailable")
        self.enqueue(queue_enabled=True,now_epoch=140)
        scratch=Path(self.temp.name)/"independent-runtime"
        scratch.mkdir()
        cwd=Path(__file__).resolve().parents[1]
        child=subprocess.run([sys.executable,"-c",_CHILD,str(self.db),
            str(self.root),str(scratch)],cwd=str(cwd),text=True,
            capture_output=True,timeout=120)
        self.assertEqual(child.returncode,0,child.stderr)
        result=json.loads(child.stdout)
        self.assertEqual(result["state"],"STAGED_OFFLINE_VALIDATED",result)
        self.assertFalse(result["active_index_updated"])
        reader=subprocess.run([sys.executable,"-c",_READ,str(self.db),
            result["job_id"]],cwd=str(cwd),text=True,capture_output=True,timeout=30)
        self.assertEqual(reader.returncode,0,reader.stderr)
        detail=json.loads(reader.stdout)
        self.assertTrue(detail["staged_offline"])
        self.assertGreater(detail["validated_counts"]["vectors"],0)
        self.assertNotIn("lease_token",detail)
        self.assertNotIn("staging_path",detail)
        self.assertEqual(inspect_job_queue(self.db)["by_state"],
                         {"STAGED_OFFLINE_VALIDATED":1})
