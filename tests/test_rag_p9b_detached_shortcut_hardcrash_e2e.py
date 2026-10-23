"""Subprocess crash around real atomic shortcut replacement, lab only."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_atomic_shortcut_restore import write_atomic_shortcut
from installer.rag_p9b_rollback_journal import RollbackJournal, read_journal


class ShortcutHardCrashTests(unittest.TestCase):
    def test_real_atomic_shortcut_crash_and_fresh_process_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            shortcut=root/"CodeBridge.lnk"
            shortcut.write_bytes(b"candidate")
            journal=root/"shell-journal.jsonl"
            source=str(Path(__file__).resolve().parents[1])
            env=dict(os.environ)
            env["PYTHONPATH"]=source+os.pathsep+env.get("PYTHONPATH","")
            crash=(
                "import os,sys;"
                "from pathlib import Path;"
                "from installer.rag_p9b_atomic_shortcut_restore import write_atomic_shortcut;"
                "from installer.rag_p9b_rollback_journal import RollbackJournal;"
                "j=RollbackJournal(sys.argv[2]);"
                "j('SHELL_DETACHED_COMBINED_ARMED',"
                "{'transaction_sha256':'a'*64});"
                "j('SHELL_BACKEND_ARMED',{'files':1});"
                "write_atomic_shortcut(Path(sys.argv[1]),b'original');"
                "os._exit(77)")
            first=subprocess.run([sys.executable,"-c",crash,str(shortcut),str(journal)],
                cwd=source,env=env,timeout=15,capture_output=True)
            self.assertEqual(first.returncode,77,first.stderr)
            self.assertEqual(shortcut.read_bytes(),b"original")
            self.assertEqual(read_journal(journal)["last_state"],"SHELL_BACKEND_ARMED")
            self.assertNotIn("SHELL_DETACHED_COMBINED_VERIFIED",
                             journal.read_text(encoding="utf-8"))
            resume=(
                "import sys;"
                "from pathlib import Path;"
                "from installer.rag_p9b_rollback_journal import RollbackJournal;"
                "from installer.rag_p9b_atomic_shortcut_restore import write_atomic_shortcut;"
                "j=RollbackJournal.resume(sys.argv[2],"
                "expected_transaction_sha256='a'*64);"
                "write_atomic_shortcut(Path(sys.argv[1]),b'original');"
                "j('SHELL_BACKEND_WRITTEN',{});"
                "j('SHELL_DETACHED_SHELL_VERIFIED',{'postverified':True})")
            second=subprocess.run([sys.executable,"-c",resume,
                str(shortcut),str(journal)],cwd=source,env=env,
                timeout=15,capture_output=True)
            self.assertEqual(second.returncode,0,second.stderr)
            self.assertEqual(shortcut.read_bytes(),b"original")
            self.assertEqual(read_journal(journal)["last_state"],
                             "SHELL_DETACHED_SHELL_VERIFIED")
            self.assertNotIn("SHELL_DETACHED_COMBINED_VERIFIED",
                             journal.read_text(encoding="utf-8"))


if __name__=="__main__":
    unittest.main()
