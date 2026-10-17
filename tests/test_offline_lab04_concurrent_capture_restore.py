import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture,OfflineFixtureError
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot,OfflineFixtureRestoreError

LOCK_CHILD = """
import sys
from rag.runtime.generation_process_lock import generation_lock
with generation_lock(sys.argv[1], 'offline_capture', exclusive=True):
    print('LOCKED', flush=True)
    sys.stdin.readline()
"""

class Lab04ConcurrentCaptureRestore(unittest.TestCase):
    def test_external_lock_blocks_both_then_allows_recovery(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-race-") as temp:
            root=Path(temp)/"codebridge-rag-generation-test"
            create_bundle(root,[("alpha","one","synthetic")])
            capture_fixture(root,"baseline")
            child=subprocess.Popen(
                [sys.executable,"-c",LOCK_CHILD,str(root)],
                cwd=str(Path(__file__).resolve().parents[1]),
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(),"LOCKED")
                with self.assertRaises(OfflineFixtureError):
                    capture_fixture(root,"blocked_capture")
                with self.assertRaises(OfflineFixtureRestoreError):
                    restore_fixture_snapshot(root,"baseline","blocked_restore")
                self.assertFalse((root/"offline-fixture-backups"/"blocked_capture").exists())
                self.assertFalse((root/"offline-fixture-restores"/"blocked_restore").exists())
                self.assertTrue((root/"offline-fixture-backups"/"baseline"/"report.json").is_file())
            finally:
                if child.poll() is None:
                    child.stdin.write("\n")
                    child.stdin.flush()
                    child.wait(timeout=10)
                for stream in (child.stdin,child.stdout,child.stderr):
                    if stream and not stream.closed:
                        stream.close()
            self.assertEqual(child.returncode,0)
            report=restore_fixture_snapshot(root,"baseline","recovered")
            self.assertEqual(report["state"],"LAB_FIXTURE_RESTORED_NOT_ACTIVATED")
            self.assertFalse(report["production_authorized"])
            self.assertFalse((root/"active-generation.json").exists())

if __name__=="__main__":
    unittest.main()
