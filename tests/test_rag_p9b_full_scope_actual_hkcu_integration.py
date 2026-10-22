"""Combined real file and shortcut backend with actual isolated HKCU API.

Production registry paths are never opened: ScopedHKCU uses unique remap.
"""
import hashlib
import sys
import unittest
from pathlib import Path

from test_rag_p9b_combined_real_backend_integration import CombinedRealBackendTests
from test_rag_p9b_real_hkcu_isolated import RealHKCUIsolatedTests
from installer.rag_p9b_shell_snapshot import snapshot_shell_state
from installer.rag_p9b_crash_preimage import create_crash_preimage
from installer.rag_p9b_combined_recovery_lab import recover_combined_lab
from installer.rag_p9b_shell_postverify import verify_restored_shell
from installer.rag_p9b_rollback_journal import read_journal
from installer.rag_p9b_windows_shell_scope import APP_KEYS
from zipfile import ZipFile
import subprocess,time,tempfile
import json,os


@unittest.skipUnless(sys.platform=="win32","real HKCU requires Windows")
class FullScopeActualHKCUTests(unittest.TestCase):
    file_worker=CombinedRealBackendTests.file_worker
    shell_worker=CombinedRealBackendTests.shell_worker
    postverify=CombinedRealBackendTests.postverify
    def setUp(self):
        CombinedRealBackendTests.setUp(self)
        RealHKCUIsolatedTests.setUp(self)
        self.reg=self.adapter
        snapshot_shell_state(appdata=self.appdata,desktop=self.desktop,
            snapshot=self.shell_zip,
            registry_values=lambda key,names:self.reg.read_key(key))
        self.shell_sha=hashlib.sha256(self.shell_zip.read_bytes()).hexdigest()
        self.preimage.unlink()
        pre=create_crash_preimage(appdata=self.appdata,desktop=self.desktop,
                                   registry=self.reg,output=self.preimage)
        self.assertTrue(pre["created"])
        self.pre_sha=pre["sha256"]
        self.reg.replace_key(APP_KEYS[0],{"exists":True,"values":{}})
        stage=Path(os.environ["LOCALAPPDATA"])/"CodeBridge-MCP-Bridge"/"release_staging"/"P9B_CURRENT_2d99ed4"
        self.files_zip=stage/"FULL_NSIS_PREINSTALL_SNAPSHOT.zip"
        self.file_sha=hashlib.sha256(self.files_zip.read_bytes()).hexdigest()
        with ZipFile(self.files_zip) as z:
            manifest=json.loads(z.read("manifest.json"))
            for rel,meta in manifest["existing"].items():
                path=self.lab.joinpath(*rel.split("/"))
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(z.read("old/"+rel))
            for rel in manifest["targets"]:
                if rel not in manifest["existing"]:
                    path=self.lab.joinpath(*rel.split("/"))
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_bytes(b"P9B_LAB_INSTALLER_CREATED_V1")
            self.old_example=next(iter(manifest["existing"]))
            self.lab.joinpath(*self.old_example.split("/")).write_bytes(b"changed-by-interrupted-nsis")
        self.expected_existing=236
        self.expected_new=22

    def tearDown(self):
        RealHKCUIsolatedTests.tearDown(self)

    def postverify(self):
        from installer.rag_p9b_shell_postverify import verify_restored_shell
        from installer.rag_p9b_installer_rollback_scope import verify_installer_rollback_snapshot
        shell=verify_restored_shell(self.shell_zip,appdata=self.appdata,
            desktop=self.desktop,registry_values=lambda key,names:self.reg.read_key(key))
        with ZipFile(self.files_zip) as z:
            m=json.loads(z.read("manifest.json"))
            olds=all(hashlib.sha256(self.lab.joinpath(*n.split("/")).read_bytes()).hexdigest()==info["sha256"] for n,info in m["existing"].items())
            fresh=all(not self.lab.joinpath(*n.split("/")).exists() for n in m["targets"] if n not in m["existing"])
        return {"verified":shell.get("verified") is True and olds and fresh}

    def test_isolated_real_hkcu_and_files_combined(self):
        r=recover_combined_lab(file_worker=self.file_worker,shell_worker=self.shell_worker,
            verify_worker=self.postverify,journal=self.journal,independent=True,
            lab_attestation={"purpose":"P9B_DISPOSABLE_UNIFIED_LAB"})
        self.assertEqual(r["state"],"COMBINED_LAB_RECOVERY_VERIFIED")
        self.assertTrue(r["verified"])
        self.assertEqual((r["files"],r["new_targets"],r["shortcuts"],r["fake_registry_keys"]),(236,22,5,2))
        self.assertEqual(read_journal(self.journal_path)["count"],6)
        for key in APP_KEYS:
            self.assertEqual(self.reg.read_key(key),{"exists":False,"values":{}})
    def test_genuine_nsis_258_crash_then_combined_real_hkcu_restore(self):
        # Use ONLY temporary lab paths; never invoke the official NSIS EXE.
        makensis=Path("C:/Program Files (x86)/NSIS/makensis.exe")
        if not makensis.is_file():
            self.skipTest("NSIS compiler not installed")
        with ZipFile(self.files_zip) as z:
            manifest=json.loads(z.read("manifest.json"))
            new=[n for n in manifest["targets"] if n not in manifest["existing"]]
            old=list(manifest["existing"])
        # Reset 22 targets: NSIS, not the test fixture, must actually create them.
        for rel in new:self.lab.joinpath(*rel.split("/")).unlink()
        first_old=old[0]
        target=self.lab.joinpath(*first_old.split("/"))
        before=target.read_bytes()
        with tempfile.TemporaryDirectory(prefix="P9B_REAL_NSIS_") as builddir:
            stage=Path(builddir)
            payload=stage/"sentinel.txt"
            payload.write_bytes(b"P9B_LAB_INSTALLER_CREATED_V1")
            nsi=stage/"isolated.nsi"
            exe=stage/"isolated.exe"
            ordered=new+[first_old]+old[1:]
            lines=['Unicode True','Name "P9B Fullscope HKCU Lab"',
                   f'OutFile "{exe}"',f'InstallDir "{self.lab}"',
                   'RequestExecutionLevel user','SilentInstall silent','Section']
            for index,rel in enumerate(ordered):
                path=self.lab.joinpath(*rel.split("/"))
                lines.append(f'SetOutPath "{path.parent}"')
                lines.append(f'File /oname={path.name} "{payload}"')
                if index==22:lines.append('Sleep 15000')
            lines.append('SectionEnd')
            nsi.write_text(chr(10).join(lines)+chr(10),encoding="ascii")
            compilation=subprocess.run([str(makensis),str(nsi)],capture_output=True,timeout=45)
            self.assertEqual(compilation.returncode,0,compilation.stderr[-200:])
            proc=subprocess.Popen([str(exe),"/S"])
            try:
                cutoff=time.monotonic()+10
                while time.monotonic()<cutoff:
                    if target.read_bytes()==payload.read_bytes():break
                    if proc.poll() is not None:self.fail("NSIS exited before interruption")
                    time.sleep(.04)
                self.assertEqual(target.read_bytes(),payload.read_bytes())
                self.assertIsNone(proc.poll(),"NSIS finished before interruption")
                proc.kill()
                proc.wait(timeout=5)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)
        self.assertTrue(all(self.lab.joinpath(*n.split("/")).is_file() for n in new))
        self.assertNotEqual(target.read_bytes(),before)
        self.journal("SHELL_NSIS_LAB_INTERRUPTED",{"files_new":22,"old_touched":1,
            "nsis_exit":proc.returncode,"scope":"DISPOSABLE_ONLY"})
        # Combined recovery with independent checks; this test process remains the coordinator.
        result=recover_combined_lab(file_worker=self.file_worker,
            shell_worker=self.shell_worker,verify_worker=self.postverify,
            journal=self.journal,independent=True,
            lab_attestation={"purpose":"P9B_DISPOSABLE_UNIFIED_LAB"})
        self.assertEqual(result["state"],"COMBINED_LAB_RECOVERY_VERIFIED")
        self.assertEqual((result["files"],result["new_targets"],result["shortcuts"],
                          result["fake_registry_keys"]),(236,22,5,2))
        self.assertTrue(self.postverify()["verified"])
        self.assertEqual(read_journal(self.journal_path)["count"],7)
        # Re-open the restored files and live isolated HKCU from a fresh
        # interpreter, with no reliance on in-process cached postchecks.
        inspector=Path.cwd()/"installer"/"rag_p9b_external_lab_postverify.py"
        child=subprocess.run([__import__("sys").executable,str(inspector),str(self.lab),
            str(self.files_zip),str(self.shell_zip),str(self.appdata),
            str(self.desktop),self.token,self.file_sha,self.shell_sha,str(self.journal_path)],capture_output=True,text=True,timeout=40)
        self.assertEqual(child.returncode,0,child.stderr[-500:]+child.stdout[-500:])
        report=json.loads(child.stdout.strip())
        self.assertEqual(report["state"],"P9B_EXTERNAL_LAB_POSTVERIFY_MATCHED")
        self.assertEqual((report["old_files"],report["new_targets_absent"],
                          report["shortcuts"],report["hkcu_keys"]),(236,22,5,2))

    def test_foreign_file_refuses_before_real_hkcu(self):
        with ZipFile(self.files_zip) as z:
            m=json.loads(z.read("manifest.json"))
            target=next(x for x in m["targets"] if x not in m["existing"])
        self.lab.joinpath(*target.split("/")).write_bytes(b"foreign")
        r=recover_combined_lab(file_worker=self.file_worker,shell_worker=self.shell_worker,
            verify_worker=self.postverify,journal=self.journal,independent=True,
            lab_attestation={"purpose":"P9B_DISPOSABLE_UNIFIED_LAB"})
        self.assertEqual(r["reason"],"FILE_RESTORE_NOT_VERIFIED")
        self.assertTrue(self.reg.read_key(APP_KEYS[0])["exists"])
