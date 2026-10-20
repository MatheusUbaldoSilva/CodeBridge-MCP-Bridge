"""Standalone worker CLI is fail-closed without explicit dual opt-in."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class OfflineWorkerCliTests(unittest.TestCase):
    def test_disabled_entrypoint_does_not_touch_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"CodeBridge-MCP-Bridge"
            db=Path(tmp)/"jobs"/"incremental_jobs.sqlite3"
            command=[sys.executable,"-m","rag.runtime.incremental_offline_worker",
                     "--project-root",str(root),"--db-path",str(db)]
            for flags in ((),("--enable-queue",),("--enable-offline-worker",)):
                cp=subprocess.run(command+list(flags),capture_output=True,text=True,
                    cwd=str(Path(__file__).resolve().parents[1]),timeout=30)
                self.assertEqual(cp.returncode,0,cp.stderr)
                self.assertEqual(json.loads(cp.stdout)["state"],"OFFLINE_WORKER_DISABLED")
                self.assertFalse(db.exists())
