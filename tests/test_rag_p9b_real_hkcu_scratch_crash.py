"""Crash and replay in a random Windows HKCU scratch key with durable journal."""
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


@unittest.skipUnless(sys.platform == "win32", "Windows registry only")
class RealHKCUScratchCrashTests(unittest.TestCase):
    def test_hard_exit_durable_journal_then_replay(self):
        import winreg
        from installer.rag_p9b_rollback_journal import RollbackJournal, read_journal

        key = r"Software\CodeBridgeP9BScratch_" + uuid.uuid4().hex
        repo = Path(__file__).resolve().parents[1]
        transaction = "a" * 64
        with tempfile.TemporaryDirectory(prefix="p9b_real_hkcu_lab_") as folder:
            root = Path(folder)
            script = root / "worker.py"
            worker_source = [
                "import os,sys,winreg",
                "from installer.rag_p9b_rollback_journal import RollbackJournal",
                "key,mode,journal_path,expected=sys.argv[1:]",
                'if not key.startswith("Software\\\\CodeBridgeP9BScratch_"):raise SystemExit(21)',
                'if mode=="crash":',
                '    j=RollbackJournal(journal_path)',
                '    j("SHELL_DETACHED_COMBINED_ARMED",{"transaction_sha256":expected})',
                '    j("SHELL_REGISTRY_SCRATCH_PREIMAGE_DURABLE",{})',
                '    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,key,0,winreg.KEY_READ|winreg.KEY_WRITE) as h:',
                '        winreg.SetValueEx(h,"State",0,winreg.REG_SZ,"partial")',
                '    os._exit(82)',
                'if mode!="replay":raise SystemExit(22)',
                'j=RollbackJournal.resume(journal_path,expected_transaction_sha256=expected)',
                'with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as h:',
                '    assert winreg.QueryValueEx(h,"State")==("partial",winreg.REG_SZ)',
                'with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key,0,winreg.KEY_READ|winreg.KEY_WRITE) as h:',
                '    winreg.SetValueEx(h,"State",0,winreg.REG_SZ,"baseline")',
                'j("SHELL_DETACHED_COMBINED_VERIFIED",{"postverified":True})',
            ]
            script.write_text("\n".join(worker_source)+"\n", encoding="utf-8")
            journal = root / "journal.jsonl"

            def run(mode):
                env = dict(os.environ)
                env["PYTHONPATH"] = str(repo) + os.pathsep + env.get("PYTHONPATH", "")
                return subprocess.run([sys.executable,str(script),key,mode,
                    str(journal),transaction],cwd=repo,env=env,
                    capture_output=True,text=True,timeout=15)

            try:
                with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,key,0,
                        winreg.KEY_READ|winreg.KEY_WRITE) as handle:
                    winreg.SetValueEx(handle,"State",0,winreg.REG_SZ,"baseline")
                first=run("crash")
                self.assertEqual(first.returncode,82,first.stderr)
                self.assertEqual(read_journal(journal)["last_state"],
                                 "SHELL_REGISTRY_SCRATCH_PREIMAGE_DURABLE")
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as handle:
                    self.assertEqual(winreg.QueryValueEx(handle,"State")[0],"partial")
                second=run("replay")
                self.assertEqual(second.returncode,0,second.stderr)
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as handle:
                    self.assertEqual(winreg.QueryValueEx(handle,"State"),
                                     ("baseline",winreg.REG_SZ))
                self.assertEqual(read_journal(journal)["last_state"],
                                 "SHELL_DETACHED_COMBINED_VERIFIED")
                with self.assertRaises(ValueError):
                    RollbackJournal.resume(journal,
                        expected_transaction_sha256=transaction)
            finally:
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key)
                except FileNotFoundError:
                    pass
            with self.assertRaises(FileNotFoundError):
                winreg.OpenKey(winreg.HKEY_CURRENT_USER,key)


if __name__ == "__main__":
    unittest.main()
