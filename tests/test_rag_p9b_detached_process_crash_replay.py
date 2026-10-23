"""Real subprocess hard-exit test. Never starts the installed CodeBridge."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_rollback_journal import RollbackJournal, read_journal


class DetachedCrashReplayTests(unittest.TestCase):
    def test_external_python_hard_exit_preserves_fsynced_journal(self):
        with tempfile.TemporaryDirectory() as d:
            journal = Path(d) / "crash.jsonl"
            root = str(Path(__file__).resolve().parents[1])
            child = (
                "import os,sys;"
                "from installer.rag_p9b_rollback_journal import RollbackJournal;"
                "j=RollbackJournal(sys.argv[1]);"
                "j('SHELL_DETACHED_LIFECYCLE_ARMED',{});"
                "j('SHELL_DETACHED_SHUTDOWN_SIGNALED',{});"
                "os._exit(73)"
            )
            env = dict(os.environ)
            env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
            result = subprocess.run(
                [sys.executable, "-c", child, str(journal)],
                cwd=root, env=env, timeout=15, capture_output=True)
            self.assertEqual(result.returncode, 73, result.stderr)
            observed = read_journal(journal)
            self.assertEqual(observed["state"], "JOURNAL_OBSERVED_ONLY")
            self.assertEqual(observed["count"], 2)
            self.assertEqual(observed["last_state"],
                             "SHELL_DETACHED_SHUTDOWN_SIGNALED")
            resumed = RollbackJournal.resume(journal)
            self.assertTrue(resumed.resumed)
            resumed("SHELL_DETACHED_LIFECYCLE_REVIEW_REQUIRED", {})
            final = read_journal(journal)
            self.assertEqual(final["count"], 3)
            self.assertEqual(final["last_state"],
                             "SHELL_DETACHED_LIFECYCLE_REVIEW_REQUIRED")

    def test_external_combined_rollback_hard_exit_is_not_completion(self):
        with tempfile.TemporaryDirectory() as d:
            journal = Path(d) / "partial-combined.jsonl"
            root = str(Path(__file__).resolve().parents[1])
            child = (
                "import os,sys;"
                "from installer.rag_p9b_rollback_journal import RollbackJournal;"
                "j=RollbackJournal(sys.argv[1]);"
                "j('SHELL_DETACHED_COMBINED_ARMED',"
                "{'transaction_sha256':'a'*64});"
                "j('SHELL_PRODUCTION_FILE_RESTORED',{'postverified':True});"
                "os._exit(74)"
            )
            env = dict(os.environ)
            env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
            result = subprocess.run(
                [sys.executable, "-c", child, str(journal)],
                cwd=root, env=env, timeout=15, capture_output=True)
            self.assertEqual(result.returncode,74,result.stderr)
            observed = read_journal(journal)
            self.assertEqual(observed["count"],2)
            self.assertEqual(observed["last_state"],"SHELL_PRODUCTION_FILE_RESTORED")
            with self.assertRaises(ValueError):
                RollbackJournal.resume(journal,expected_transaction_sha256="b"*64)
            resumed = RollbackJournal.resume(
                journal,expected_transaction_sha256="a"*64)
            self.assertTrue(resumed.resumed)
            self.assertEqual(resumed.bound_transaction_sha256,"a"*64)
            self.assertNotIn("SHELL_DETACHED_COMBINED_VERIFIED",
                             journal.read_text(encoding="utf-8"))

    def test_hard_exit_bound_lifecycle_replay_wrong_identity_refused(self):
        with tempfile.TemporaryDirectory() as d:
            journal=Path(d)/"bound-crash.jsonl"
            repo=str(Path(__file__).resolve().parents[1])
            child=(
                "import os,sys;"
                "from installer.rag_p9b_rollback_journal import RollbackJournal;"
                "j=RollbackJournal(sys.argv[1]);"
                "j('SHELL_DETACHED_LIFECYCLE_ARMED',"
                "{'transaction_sha256':'a'*64});"
                "j('SHELL_DETACHED_SHUTDOWN_SIGNALED',{});"
                "os._exit(76)")
            env=dict(os.environ)
            env["PYTHONPATH"]=repo+os.pathsep+env.get("PYTHONPATH","")
            process=subprocess.run([sys.executable,"-c",child,str(journal)],
                cwd=repo,env=env,capture_output=True,timeout=15)
            self.assertEqual(process.returncode,76,process.stderr)
            self.assertEqual(read_journal(journal)["count"],2)
            with self.assertRaises(ValueError):
                RollbackJournal.resume(journal,expected_transaction_sha256="b"*64)
            resumed=RollbackJournal.resume(
                journal,expected_transaction_sha256="a"*64)
            self.assertEqual(resumed.bound_transaction_sha256,"a"*64)
            self.assertEqual(resumed._sequence,2)
            self.assertNotIn("SHELL_DETACHED_GUI_RESTARTED",
                             journal.read_text(encoding="utf-8"))

    def test_external_crash_does_not_imply_restart_or_nsis(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"crash.jsonl"
            j=RollbackJournal(path)
            j("SHELL_DETACHED_LIFECYCLE_ARMED", {})
            j("SHELL_DETACHED_SHUTDOWN_SIGNALED", {})
            states=Path(path).read_text(encoding="utf-8")
            self.assertNotIn("SHELL_DETACHED_GUI_RESTARTED", states)
            self.assertNotIn("NSIS_EXECUTED", states)
            self.assertNotIn("SHELL_DETACHED_COMBINED_VERIFIED", states)


if __name__=="__main__":
    unittest.main()
