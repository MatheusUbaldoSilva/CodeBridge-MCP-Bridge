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
    def test_recovery_survives_launcher_hard_exit(self):
        f=self.fixture
        from zipfile import ZipFile
        with ZipFile(f.files_zip) as archive:
            approved_installed=json.loads(archive.read('manifest.json'))['installed_root']
        stage=f.lab.parent
        cfg=stage/'survival-config.json'
        journal=stage/'survival-journal.jsonl'
        info={'lab':str(f.lab),'appdata':str(f.appdata),'desktop':str(f.desktop),
            'token':f.token,'installed':approved_installed,
            'snapshot':str(f.files_zip),'snapshot_sha256':f.file_sha,
            'shell_snapshot':str(f.shell_zip),'shell_snapshot_sha256':f.shell_sha,
            'preimage':str(f.preimage),'preimage_sha256':f.pre_sha,
            'journal':str(journal)}
        cfg.write_text(json.dumps(info),encoding='utf-8')
        worker=Path.cwd()/'installer'/'rag_p9b_detached_combined_recovery_lab.py'
        launcher=stage/'temporary-launcher.py'
        result_file=stage/'detached-result.json'
        launcher.write_text("""
import subprocess,sys,os
from pathlib import Path
output=open(sys.argv[3],'wb')
subprocess.Popen([sys.executable,sys.argv[1],sys.argv[2]],
                 creationflags=getattr(subprocess,'DETACHED_PROCESS',0),
                 stdin=subprocess.DEVNULL,stdout=output,stderr=output,
                 close_fds=True)
output.close()
os._exit(83)
""",encoding='utf-8')
        initiator=subprocess.run([sys.executable,str(launcher),str(worker),
            str(cfg),str(result_file)],capture_output=True,timeout=15)
        self.assertEqual(initiator.returncode,83)
        import time
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if result_file.is_file():
                try:
                    message=json.loads(result_file.read_text(encoding='utf-8').strip())
                    if message.get('state')=='COMBINED_LAB_RECOVERY_VERIFIED':
                        break
                except (ValueError,UnicodeDecodeError):
                    pass
            time.sleep(.1)
        else:
            self.fail('RECOVERER_DID_NOT_FINISH_AFTER_LAUNCHER_EXIT')
        self.assertTrue(message['verified'])
        self.assertTrue(message['detached_process'])
        self.assertEqual((message['files'],message['new_targets'],message['shortcuts'],
                          message['fake_registry_keys']),(236,22,5,2))
        self.assertTrue(verify_restored_shell(f.shell_zip,appdata=f.appdata,
            desktop=f.desktop,registry_values=lambda k,n:f.reg.read_key(k))['verified'])

    def test_detached_recovery_replays_incomplete_journal(self):
        from zipfile import ZipFile
        from installer.rag_p9b_rollback_journal import RollbackJournal,read_journal
        f=self.fixture
        with ZipFile(f.files_zip) as archive:
            approved_installed=json.loads(archive.read('manifest.json'))['installed_root']
        folder=f.lab.parent
        config=folder/'replay-config.json'
        journal=folder/'replay-journal.jsonl'
        settings={'lab':str(f.lab),'appdata':str(f.appdata),'desktop':str(f.desktop),
                  'token':f.token,'installed':approved_installed,
                  'snapshot':str(f.files_zip),'snapshot_sha256':f.file_sha,
                  'shell_snapshot':str(f.shell_zip),'shell_snapshot_sha256':f.shell_sha,
                  'preimage':str(f.preimage),'preimage_sha256':f.pre_sha,
                  'journal':str(journal)}
        config.write_text(json.dumps(settings),encoding='utf-8')
        first=RollbackJournal(journal)
        first('SHELL_COMBINED_RECOVERY_ARMED',{})
        first('SHELL_COMBINED_FILE_CHECKED',{'postverified':False})
        worker=Path.cwd()/'installer'/'rag_p9b_detached_combined_recovery_lab.py'
        child=subprocess.run([sys.executable,str(worker),str(config)],
                              capture_output=True,text=True,timeout=40)
        self.assertEqual(child.returncode,0,child.stdout[-650:]+child.stderr[-650:])
        outcome=json.loads(child.stdout.strip())
        self.assertTrue(outcome['verified'])
        proof=read_journal(journal)
        self.assertEqual(proof['count'],8)
        self.assertEqual(proof['last_state'],'SHELL_COMBINED_RECOVERY_VERIFIED')
        refused=subprocess.run([sys.executable,str(worker),str(config)],
                               capture_output=True,text=True,timeout=40)
        self.assertEqual(refused.returncode,2)
        self.assertEqual(json.loads(refused.stdout.strip())['reason'],'DETACHED_EXCEPTION')

    def test_denies_production_root(self):
        f=self.fixture
        config=f.lab.parent/'invalid.json'
        config.write_text(json.dumps({'lab':str(f.installed)}),encoding='utf-8')
        worker=Path.cwd()/'installer'/'rag_p9b_detached_combined_recovery_lab.py'
        r=subprocess.run([sys.executable,str(worker),str(config)],capture_output=True,text=True,timeout=30)
        self.assertEqual(r.returncode,2)

if __name__=='__main__':unittest.main()
