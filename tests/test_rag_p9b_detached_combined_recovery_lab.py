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

    def _run_real_nsis_interrupted(self, crash_recoverer=False):
        import tempfile,time
        from zipfile import ZipFile
        from installer.rag_p9b_rollback_journal import RollbackJournal,read_journal
        compiler=Path('C:/Program Files (x86)/NSIS/makensis.exe')
        if not compiler.exists():
            self.skipTest('Windows NSIS not installed')
        f=self.fixture
        with ZipFile(f.files_zip) as archive:
            manifest=json.loads(archive.read('manifest.json'))
        approved=manifest['installed_root']
        old=list(manifest['existing'])
        new=[n for n in manifest['targets'] if n not in manifest['existing']]
        self.assertEqual((len(old),len(new)),(236,22))
        for rel in new:
            f.lab.joinpath(*rel.split('/')).unlink()
        prior_file=f.lab.joinpath(*old[0].split('/'))
        before=prior_file.read_bytes()
        with tempfile.TemporaryDirectory(prefix='P9B_NSIS_DETACHED_') as folder:
            stage=Path(folder)
            exe=stage/'nsis-lab.exe'
            payload=stage/'test-payload.txt'
            payload.write_bytes(b'P9B_LAB_INSTALLER_CREATED_V1')
            script=stage/'nsis-lab.nsi'
            lines=['Unicode True','Name "P9B Detached Fullscope"',
                   f'OutFile "{exe}"',f'InstallDir "{f.lab}"',
                   'RequestExecutionLevel user','SilentInstall silent','Section']
            for index,rel in enumerate(new+[old[0]]+old[1:]):
                path=f.lab.joinpath(*rel.split('/'))
                lines.append(f'SetOutPath "{path.parent}"')
                lines.append(f'File /oname={path.name} "{payload}"')
                if index==22:lines.append('Sleep 15000')
            lines.append('SectionEnd')
            script.write_text(chr(10).join(lines)+chr(10),encoding='ascii')
            built=subprocess.run([str(compiler),str(script)],capture_output=True,timeout=45)
            self.assertEqual(built.returncode,0,built.stderr[-650:])
            process=subprocess.Popen([str(exe),'/S'])
            try:
                deadline=time.monotonic()+12
                while time.monotonic()<deadline:
                    if prior_file.read_bytes()==payload.read_bytes():break
                    if process.poll() is not None:self.fail('NSIS_EXITED_EARLY')
                    time.sleep(.05)
                self.assertEqual(prior_file.read_bytes(),payload.read_bytes())
                self.assertIsNone(process.poll())
                process.kill();process.wait(timeout=5)
            finally:
                if process.poll() is None:
                    process.kill();process.wait(timeout=5)
        self.assertNotEqual(prior_file.read_bytes(),before)
        self.assertTrue(all(f.lab.joinpath(*x.split('/')).is_file() for x in new))
        folder=f.lab.parent
        cfg=folder/'actual-nsis-detached.json'
        journal=folder/'actual-nsis-journal.jsonl'
        settings={'lab':str(f.lab),'appdata':str(f.appdata),
          'desktop':str(f.desktop),'token':f.token,'installed':approved,
          'snapshot':str(f.files_zip),'snapshot_sha256':f.file_sha,
          'shell_snapshot':str(f.shell_zip),'shell_snapshot_sha256':f.shell_sha,
          'preimage':str(f.preimage),'preimage_sha256':f.pre_sha,
          'journal':str(journal)}
        cfg.write_text(json.dumps(settings),encoding='utf-8')
        start=RollbackJournal(journal)
        start('SHELL_NSIS_LAB_INTERRUPTED',{'files':258})
        worker=Path.cwd()/'installer'/'rag_p9b_detached_combined_recovery_lab.py'
        if crash_recoverer:
            env=os.environ.copy()
            env["P9B_LAB_FAULT_AFTER_SHELL"]="1"
            crashed=subprocess.run([sys.executable,str(worker),str(cfg)],
                capture_output=True,text=True,timeout=45,env=env)
            self.assertEqual(crashed.returncode,88,crashed.stderr[-700:])
            self.assertNotEqual(read_journal(journal)["last_state"],
                                "SHELL_COMBINED_RECOVERY_VERIFIED")
        recovered=subprocess.run([sys.executable,str(worker),str(cfg)],
                                 capture_output=True,text=True,timeout=45)
        self.assertEqual(recovered.returncode,0,recovered.stdout[-700:]+recovered.stderr[-700:])
        result=json.loads(recovered.stdout.strip())
        self.assertTrue(result['verified'])
        self.assertEqual((result['files'],result['new_targets'],
            result['shortcuts'],result['fake_registry_keys']),(236,22,5,2))
        observed=read_journal(journal)
        self.assertGreaterEqual(observed['count'],7)
        self.assertEqual(observed['last_state'],'SHELL_COMBINED_RECOVERY_VERIFIED')
        with ZipFile(f.files_zip) as archive:
            expected_original=archive.read('old/'+old[0])
        self.assertEqual(prior_file.read_bytes(),expected_original)

    def test_actual_nsis_interruption_recovers_in_external_child(self):
        self._run_real_nsis_interrupted()

    def test_actual_nsis_then_recoverer_hardcrash_replays(self):
        self._run_real_nsis_interrupted(crash_recoverer=True)
    def test_recoverer_crash_after_files_then_replays_full_shell(self):
        from zipfile import ZipFile
        from installer.rag_p9b_rollback_journal import read_journal
        f=self.fixture
        with ZipFile(f.files_zip) as archive:
            installed_from_manifest=json.loads(archive.read('manifest.json'))['installed_root']
        base=f.lab.parent
        config=base/'worker-crash.json'
        journal=base/'worker-crash-journal.jsonl'
        config.write_text(json.dumps({
            'lab':str(f.lab),'appdata':str(f.appdata),'desktop':str(f.desktop),
            'token':f.token,'installed':installed_from_manifest,
            'snapshot':str(f.files_zip),'snapshot_sha256':f.file_sha,
            'shell_snapshot':str(f.shell_zip),'shell_snapshot_sha256':f.shell_sha,
            'preimage':str(f.preimage),'preimage_sha256':f.pre_sha,
            'journal':str(journal)}),encoding='utf-8')
        worker=Path.cwd()/'installer'/'rag_p9b_detached_combined_recovery_lab.py'
        env=os.environ.copy()
        env['P9B_LAB_FAULT_AFTER_FILES']='1'
        crashed=subprocess.run([sys.executable,str(worker),str(config)],
           capture_output=True,text=True,timeout=45,env=env)
        self.assertEqual(crashed.returncode,87)
        self.assertEqual(read_journal(journal)['count'],1)
        resumed=subprocess.run([sys.executable,str(worker),str(config)],
           capture_output=True,text=True,timeout=45)
        self.assertEqual(resumed.returncode,0,resumed.stdout[-600:]+resumed.stderr[-600:])
        result=json.loads(resumed.stdout.strip())
        self.assertTrue(result['verified'])
        self.assertEqual((result['files'],result['new_targets'],
            result['shortcuts'],result['fake_registry_keys']),(236,22,5,2))
        self.assertEqual(read_journal(journal)['last_state'],'SHELL_COMBINED_RECOVERY_VERIFIED')

    def test_recoverer_crash_after_shell_then_replays(self):
        from zipfile import ZipFile
        from installer.rag_p9b_rollback_journal import read_journal
        f=self.fixture
        with ZipFile(f.files_zip) as archive:
            approved=json.loads(archive.read('manifest.json'))['installed_root']
        base=f.lab.parent;cfg=base/'shell-crash-config.json';journal=base/'shell-crash-log.jsonl'
        payload={'lab':str(f.lab),'appdata':str(f.appdata),'desktop':str(f.desktop),
            'token':f.token,'installed':approved,
            'snapshot':str(f.files_zip),'snapshot_sha256':f.file_sha,
            'shell_snapshot':str(f.shell_zip),'shell_snapshot_sha256':f.shell_sha,
            'preimage':str(f.preimage),'preimage_sha256':f.pre_sha,
            'journal':str(journal)}
        cfg.write_text(json.dumps(payload),encoding='utf-8')
        worker=Path.cwd()/'installer'/'rag_p9b_detached_combined_recovery_lab.py'
        env=os.environ.copy();env['P9B_LAB_FAULT_AFTER_SHELL']='1'
        interrupted=subprocess.run([sys.executable,str(worker),str(cfg)],
             capture_output=True,text=True,timeout=45,env=env)
        self.assertEqual(interrupted.returncode,88)
        self.assertEqual(read_journal(journal)['last_state'],'SHELL_BACKEND_WRITTEN')
        resumed=subprocess.run([sys.executable,str(worker),str(cfg)],
             capture_output=True,text=True,timeout=45)
        self.assertEqual(resumed.returncode,0,resumed.stdout[-400:]+resumed.stderr[-400:])
        report=json.loads(resumed.stdout.strip())
        self.assertTrue(report['verified'])
        self.assertEqual((report['files'],report['new_targets'],
           report['shortcuts'],report['fake_registry_keys']),(236,22,5,2))
        self.assertEqual(read_journal(journal)['last_state'],'SHELL_COMBINED_RECOVERY_VERIFIED')

    def test_denies_production_root(self):
        f=self.fixture
        config=f.lab.parent/'invalid.json'
        config.write_text(json.dumps({'lab':str(f.installed)}),encoding='utf-8')
        worker=Path.cwd()/'installer'/'rag_p9b_detached_combined_recovery_lab.py'
        r=subprocess.run([sys.executable,str(worker),str(config)],capture_output=True,text=True,timeout=30)
        self.assertEqual(r.returncode,2)

if __name__=='__main__':unittest.main()
