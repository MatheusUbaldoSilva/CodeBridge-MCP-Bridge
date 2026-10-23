"""Real Windows scratch HKCU and disposable file combined crash/replay."""
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


@unittest.skipUnless(sys.platform=="win32", "Windows HKCU required")
class CombinedRealScratchRollbackTests(unittest.TestCase):
    def test_file_and_real_scratch_hkcu_crash_and_resume(self):
        import winreg
        from installer.rag_p9b_rollback_journal import RollbackJournal, read_journal
        repo=Path(__file__).resolve().parents[1]
        key=r"Software\CodeBridgeP9BScratch_"+uuid.uuid4().hex
        sha="b"*64
        with tempfile.TemporaryDirectory(prefix="p9b_real_combined_") as dirname:
            root=Path(dirname)
            file=root/"demo.txt"
            file.write_bytes(b"BASELINE")
            preimage=root/"original.bin"
            preimage.write_bytes(file.read_bytes())
            journal=root/"events.jsonl"
            worker=root/"worker.py"
            worker.write_text("\n".join([
                "import os,sys,winreg",
                "from pathlib import Path",
                "from installer.rag_p9b_rollback_journal import RollbackJournal",
                "key,mode,root_string,expected=sys.argv[1:]",
                'if not key.startswith("Software\\\\CodeBridgeP9BScratch_"):raise SystemExit(21)',
                "root=Path(root_string)",
                'target=root/"demo.txt"',
                'pre=root/"original.bin"',
                'log=root/"events.jsonl"',
                'if mode=="crash":',
                '    j=RollbackJournal(log)',
                '    j("SHELL_DETACHED_COMBINED_ARMED",{"transaction_sha256":expected})',
                '    j("SHELL_REAL_SCRATCH_PREIMAGE_ARMED",{})',
                '    target.write_bytes(b"PARTIAL")',
                '    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,key,0,winreg.KEY_READ|winreg.KEY_WRITE) as h:',
                '        winreg.SetValueEx(h,"State",0,winreg.REG_SZ,"PARTIAL")',
                '    os._exit(83)',
                'if mode!="resume":raise SystemExit(22)',
                'j=RollbackJournal.resume(log,expected_transaction_sha256=expected)',
                'target.write_bytes(pre.read_bytes())',
                'with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key,0,winreg.KEY_READ|winreg.KEY_WRITE) as h:',
                '    winreg.SetValueEx(h,"State",0,winreg.REG_SZ,"BASELINE")',
                'assert target.read_bytes()==b"BASELINE"',
                'with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as h:',
                '    assert winreg.QueryValueEx(h,"State")==("BASELINE",winreg.REG_SZ)',
                'j("SHELL_DETACHED_COMBINED_VERIFIED",{"postverified":True})',
            ])+"\n",encoding="utf-8")
            def run(mode):
                env=dict(os.environ)
                env["PYTHONPATH"]=str(repo)+os.pathsep+env.get("PYTHONPATH","")
                return subprocess.run([sys.executable,str(worker),key,mode,str(root),sha],
                    env=env,cwd=repo,capture_output=True,text=True,timeout=15)
            try:
                with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,key,0,
                        winreg.KEY_READ|winreg.KEY_WRITE) as h:
                    winreg.SetValueEx(h,"State",0,winreg.REG_SZ,"BASELINE")
                first=run("crash")
                self.assertEqual(first.returncode,83,first.stderr)
                self.assertEqual(file.read_bytes(),b"PARTIAL")
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as h:
                    self.assertEqual(winreg.QueryValueEx(h,"State")[0],"PARTIAL")
                self.assertEqual(read_journal(journal)["last_state"],
                    "SHELL_REAL_SCRATCH_PREIMAGE_ARMED")
                second=run("resume")
                self.assertEqual(second.returncode,0,second.stderr)
                self.assertEqual(file.read_bytes(),b"BASELINE")
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as h:
                    self.assertEqual(winreg.QueryValueEx(h,"State"),
                                     ("BASELINE",winreg.REG_SZ))
                self.assertEqual(read_journal(journal)["last_state"],
                                 "SHELL_DETACHED_COMBINED_VERIFIED")
                with self.assertRaises(ValueError):
                    RollbackJournal.resume(journal,
                        expected_transaction_sha256=sha)
            finally:
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key)
                except FileNotFoundError:
                    pass
            with self.assertRaises(FileNotFoundError):
                winreg.OpenKey(winreg.HKEY_CURRENT_USER,key)


if __name__=="__main__":
    unittest.main()
