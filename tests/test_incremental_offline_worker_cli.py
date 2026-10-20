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

            denied=subprocess.run(command+["--enable-queue","--enable-offline-worker"],
                capture_output=True,text=True,
                cwd=str(Path(__file__).resolve().parents[1]),timeout=30)
            self.assertEqual(denied.returncode,1)
            self.assertEqual(json.loads(denied.stdout)["state"],"NO_APPROVED_SOURCES")
            self.assertFalse(db.exists())

    def test_missing_runtime_backend_does_not_claim(self):
        from unittest.mock import patch
        from rag.runtime.incremental_offline_worker import process_offline_job_once
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"CodeBridge-MCP-Bridge"
            db=Path(tmp)/"jobs"/"incremental_jobs.sqlite3"
            with patch("importlib.util.find_spec", return_value=None):
                result=process_offline_job_once(
                    db,root,approved_paths=("sample.py",),
                    queue_enabled=True,worker_enabled=True)
            self.assertEqual(result["state"],"OFFLINE_WORKER_RUNTIME_UNAVAILABLE")
            self.assertFalse(db.exists())
            self.assertFalse(result["active_index_updated"])
