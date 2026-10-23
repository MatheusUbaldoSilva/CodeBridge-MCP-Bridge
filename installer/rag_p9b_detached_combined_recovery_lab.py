"""Separate-process lab rollback entrypoint (no production paths)."""
import hashlib,json,os,sys,tempfile,uuid
from pathlib import Path
from zipfile import ZipFile

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from installer.rag_p9b_combined_recovery_lab import recover_combined_lab
from installer.rag_p9b_file_restore_executor_lab import restore_files_in_lab
from installer.rag_p9b_installer_rollback_scope import verify_installer_rollback_snapshot
from installer.rag_p9b_windows_restore_backend import restore_shell
from installer.rag_p9b_shell_postverify import verify_restored_shell
from installer.rag_p9b_rollback_journal import RollbackJournal
from installer.rag_p9b_winreg_adapter import ScopedHKCU
from installer.rag_p9b_windows_shell_scope import APP_KEYS

def execute(cfg):
    denied={'state':'DETACHED_COMBINED_LAB_REFUSED','verified':False,'production_modified':False}
    try:
        c=json.loads(Path(cfg).read_text(encoding='utf-8'))
        root=Path(c['lab']).resolve()
        temp=Path(tempfile.gettempdir()).resolve()
        if root.name!='disposable' or temp not in root.parents or not root.is_dir() or root.is_symlink():
            return {**denied,'reason':'DISPOSABLE_ROOT_REQUIRED'}
        appdata=Path(c['appdata']).resolve();desktop=Path(c['desktop']).resolve()
        if not appdata.is_relative_to(root) or not desktop.is_relative_to(root):
            return {**denied,'reason':'SHELL_OUTSIDE_SCRATCH'}
        token=str(uuid.UUID(c['token'])).replace('-','')
        installed=Path(c['installed']).resolve()
        if root==installed or root.is_relative_to(installed):
            return {**denied,'reason':'LIVE_INSTALL_PATH_REJECTED'}
        paths={k:Path(c[k]) for k in ('snapshot','shell_snapshot','preimage')}
        for name,path in paths.items():
            if path.is_symlink() or not path.is_file() or len(c[name+'_sha256'])!=64 or hashlib.sha256(path.read_bytes()).hexdigest()!=c[name+'_sha256']:
                return {**denied,'reason':'BACKUP_IDENTITY_INVALID'}
        import winreg
        wr=winreg
        regroot='Software'+chr(92)+'CodeBridgeP9BLab'+chr(92)+token
        mapping={key:regroot+chr(92)+str(i) for i,key in enumerate(APP_KEYS)}
        class Remap:
            HKEY_CURRENT_USER=wr.HKEY_CURRENT_USER;REG_SZ=wr.REG_SZ;REG_DWORD=wr.REG_DWORD
            KEY_READ=wr.KEY_READ;KEY_WRITE=wr.KEY_WRITE
            QueryValueEx=staticmethod(wr.QueryValueEx);QueryInfoKey=staticmethod(wr.QueryInfoKey)
            EnumValue=staticmethod(wr.EnumValue);DeleteValue=staticmethod(wr.DeleteValue)
            SetValueEx=staticmethod(wr.SetValueEx)
            def OpenKey(self,h,k,*args):return wr.OpenKey(h,mapping[k],*args)
            def CreateKeyEx(self,h,k,*args):return wr.CreateKeyEx(h,mapping[k],*args)
            def DeleteKey(self,h,k):return wr.DeleteKey(h,mapping[k])
        registry=ScopedHKCU(Remap())
        journal_path=Path(c['journal']).absolute()
        if (journal_path.parent!=Path(cfg).resolve().parent or
                journal_path.is_symlink()):
            return {**denied,'reason':'JOURNAL_LOCATION_INVALID'}
        snapshot_proof=verify_installer_rollback_snapshot(paths['snapshot'],installed)
        if (snapshot_proof.get('verified') is not True
                or snapshot_proof.get('targets')!=258
                or snapshot_proof.get('existing_files')!=236):
            return {**denied,'reason':'OFFICIAL_SNAPSHOT_SCOPE_INVALID'}
        journal=(RollbackJournal.resume(journal_path)
                 if journal_path.exists() else RollbackJournal(journal_path))
        def file_worker():
            result=restore_files_in_lab(snapshot=paths['snapshot'],installed=installed,lab_root=root,
                expected_sha256=c['snapshot_sha256'],
                snapshot_probe=verify_installer_rollback_snapshot)
            # Explicit lab-only fault injection: a real hard exit after all
            # files restore, before the coordinator can journal completion.
            if (result.get('verified') is True and
                    os.environ.get('P9B_LAB_FAULT_AFTER_FILES')=='1'):
                os._exit(87)
            return result
        def shell_worker():
            applied=restore_shell(snapshot=paths['shell_snapshot'],
                expected_sha256=c['shell_snapshot_sha256'],appdata=appdata,
                desktop=desktop,registry=registry,installed=installed,
                stopped=True,external=True,execute=True,journal=journal,
                process_guard=lambda _: {'state':'NO_RUNNING_CODEBRIDGE'},
                preimage=paths['preimage'],preimage_sha256=c['preimage_sha256'])
            if (applied.get('state')=='SHELL_BACKEND_APPLIED_POSTVERIFY_REQUIRED'
                    and os.environ.get('P9B_LAB_FAULT_AFTER_SHELL')=='1'):
                os._exit(88)
            post=verify_restored_shell(paths['shell_snapshot'],appdata=appdata,desktop=desktop,
                registry_values=lambda k,n:registry.read_key(k))
            ok=applied.get('state')=='SHELL_BACKEND_APPLIED_POSTVERIFY_REQUIRED' and post.get('verified') is True
            return {'state':'SHELL_LAB_VERIFIED' if ok else 'SHELL_FAILED','verified':ok,
                'shortcuts':post.get('shortcuts_checked'),'registry_keys':post.get('registry_keys_checked')}
        def final_verify():
            with ZipFile(paths['snapshot']) as z:
                m=json.loads(z.read('manifest.json'))
                originals=all(hashlib.sha256(root.joinpath(*n.split('/')).read_bytes()).hexdigest()==v['sha256']
                    for n,v in m['existing'].items())
                new=all(not root.joinpath(*n.split('/')).exists()
                    for n in m['targets'] if n not in m['existing'])
            shell=verify_restored_shell(paths['shell_snapshot'],appdata=appdata,desktop=desktop,
                registry_values=lambda k,n:registry.read_key(k))
            return {'verified':originals and new and shell.get('verified') is True}
        r=recover_combined_lab(file_worker=file_worker,shell_worker=shell_worker,
            verify_worker=final_verify,journal=journal,independent=True,
            lab_attestation={'purpose':'P9B_DISPOSABLE_UNIFIED_LAB'})
        return {**r,'detached_process':True,'production_modified':False}
    except Exception as exc:
        return {**denied,'reason':'DETACHED_EXCEPTION','error_type':type(exc).__name__}

if __name__=='__main__':
    if len(sys.argv)!=2:sys.exit(2)
    result=execute(sys.argv[1])
    print(json.dumps(result,sort_keys=True))
    sys.exit(0 if result.get('verified') else 2)
