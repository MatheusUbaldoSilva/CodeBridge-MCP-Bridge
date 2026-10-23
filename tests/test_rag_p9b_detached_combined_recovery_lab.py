import hashlib,json,os,subprocess,sys,unittest
from pathlib import Path
from test_rag_p9b_full_scope_actual_hkcu_integration import FullScopeActualHKCUTests
from installer.rag_p9b_shell_postverify import verify_restored_shell

@unittest.skipUnless(sys.platform=='win32','Windows real isolated HKCU only')
class DetachedRealRegistryIntegration(unittest.TestCase):
    def setUp(self):
        self.fixture=FullScopeActualHKCUTests('test_isolated_real_hkcu_and_files_combined')
        self.fixture.setUp()
    def tearDown(self):
        self.fixture.tearDown()
        self.fixture.doCleanups()
    def test_detached_combined_recovery(self):
        f=self.fixture
        config=f.lab.parent/'detached-config.json'
        journal=f.lab.parent/'detached-journal.jsonl'
        from zipfile import ZipFile
        with ZipFile(f.files_zip) as archive:
            approved_installed=json.loads(archive.read('manifest.json'))['installed_root']
        payload={'lab':str(f.lab),'appdata':str(f.appdata),'desktop':str(f.desktop),
            'token':f.token,'installed':approved_installed,
            'snapshot':str(f.files_zip),'snapshot_sha256':f.file_sha,
            'shell_snapshot':str(f.shell_zip),'shell_snapshot_sha256':f.shell_sha,
            'preimage':str(f.preimage),'preimage_sha256':f.pre_sha,
            'journal':str(journal)}
        config.write_text(json.dumps(payload),encoding='utf-8')
        worker=Path.cwd()/'installer'/'rag_p9b_detached_combined_recovery_lab.py'
        r=subprocess.run([sys.executable,str(worker),str(config)],capture_output=True,text=True,timeout=45)
        self.assertEqual(r.returncode,0,r.stderr[-800:]+r.stdout[-800:])
        report=json.loads(r.stdout.strip())
        self.assertEqual(report['state'],'COMBINED_LAB_RECOVERY_VERIFIED')
        self.assertTrue(report['detached_process'])
        self.assertEqual((report['files'],report['new_targets'],
            report['shortcuts'],report['fake_registry_keys']),(236,22,5,2))
        from zipfile import ZipFile
        with ZipFile(f.files_zip) as archive:
            manifest=json.loads(archive.read('manifest.json'))
            newly_created=next(n for n in manifest['targets'] if n not in manifest['existing'])
        self.assertFalse(f.lab.joinpath(*newly_created.split('/')).exists())
        proof=verify_restored_shell(f.shell_zip,appdata=f.appdata,desktop=f.desktop,
            registry_values=lambda key,names:f.reg.read_key(key))
        self.assertTrue(proof['verified'])
    def test_denies_production_root(self):
        f=self.fixture
        config=f.lab.parent/'invalid.json'
        config.write_text(json.dumps({'lab':str(f.installed)}),encoding='utf-8')
        worker=Path.cwd()/'installer'/'rag_p9b_detached_combined_recovery_lab.py'
        r=subprocess.run([sys.executable,str(worker),str(config)],capture_output=True,text=True,timeout=30)
        self.assertEqual(r.returncode,2)

if __name__=='__main__':unittest.main()
