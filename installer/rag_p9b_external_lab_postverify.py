"""Read-only external postverification for P9-B full-scope Windows scratch lab.

Never opens production CodeBridge registry keys. Registry namespace is remapped
to UUID-scoped temporary HKCU names. No filesystem mutations.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
from zipfile import ZipFile

if __package__ in (None, ""):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from installer.rag_p9b_shell_postverify import verify_restored_shell
from installer.rag_p9b_windows_shell_scope import APP_KEYS
from installer.rag_p9b_winreg_adapter import ScopedHKCU
from installer.rag_p9b_rollback_journal import read_journal


def verify(*, lab, snapshot, shell_snapshot, appdata, desktop, registry_token,
           snapshot_sha256, shell_sha256, journal):
    denied={"state":"P9B_EXTERNAL_LAB_POSTVERIFY_REFUSED","verified":False}
    lab=Path(lab).resolve()
    temp=Path(tempfile.gettempdir()).resolve()
    if (temp not in lab.parents or lab.name!="disposable"
            or not lab.is_dir() or lab.is_symlink()):
        return {**denied,"reason":"SCRATCH_LAB_ONLY"}
    if (not Path(appdata).resolve().is_relative_to(lab)
            or not Path(desktop).resolve().is_relative_to(lab)):
        return {**denied,"reason":"SHELL_OUTSIDE_LAB"}
    try:
        uuid.UUID(registry_token)
    except (ValueError,TypeError,AttributeError):
        return {**denied,"reason":"REGISTRY_TOKEN_INVALID"}
    def valid_sha(expected):
        return isinstance(expected,str) and len(expected)==64 and all(ch in "0123456789abcdef" for ch in expected)
    if not valid_sha(snapshot_sha256) or not valid_sha(shell_sha256):
        return {**denied,"reason":"ARTIFACT_IDENTITY_INVALID"}
    try:
        file_hash=hashlib.sha256(Path(snapshot).read_bytes()).hexdigest()
        shell_hash=hashlib.sha256(Path(shell_snapshot).read_bytes()).hexdigest()
    except OSError:
        return {**denied,"reason":"ARTIFACT_UNREADABLE"}
    if file_hash!=snapshot_sha256 or shell_hash!=shell_sha256:
        return {**denied,"reason":"ARTIFACT_DIGEST_MISMATCH"}
    proof=read_journal(journal)
    if (proof.get("state")!="JOURNAL_OBSERVED_ONLY"
            or proof.get("count")!=7
            or proof.get("last_state")!="SHELL_COMBINED_RECOVERY_VERIFIED"):
        return {**denied,"reason":"JOURNAL_CHAIN_INCOMPLETE"}
    import winreg as wr
    root="Software"+chr(92)+"CodeBridgeP9BLab"+chr(92)+registry_token
    mapping={key:root+chr(92)+str(i) for i,key in enumerate(APP_KEYS)}
    class Remap:
        HKEY_CURRENT_USER=wr.HKEY_CURRENT_USER
        REG_SZ=wr.REG_SZ
        REG_DWORD=wr.REG_DWORD
        KEY_READ=wr.KEY_READ
        KEY_WRITE=wr.KEY_WRITE
        QueryValueEx=staticmethod(wr.QueryValueEx)
        QueryInfoKey=staticmethod(wr.QueryInfoKey)
        EnumValue=staticmethod(wr.EnumValue)
        DeleteValue=staticmethod(wr.DeleteValue)
        SetValueEx=staticmethod(wr.SetValueEx)
        def OpenKey(self,h,k,*args):
            return wr.OpenKey(h,mapping[k],*args)
        def CreateKeyEx(self,h,k,*args):
            raise RuntimeError("POSTVERIFY_READ_ONLY")
        def DeleteKey(self,h,k):
            raise RuntimeError("POSTVERIFY_READ_ONLY")
    registry=ScopedHKCU(Remap())
    try:
        with ZipFile(snapshot) as archive:
            manifest=json.loads(archive.read("manifest.json"))
            previous=manifest["existing"]
            fresh=[n for n in manifest["targets"] if n not in previous]
            old_ok=all(
                hashlib.sha256(lab.joinpath(*n.split("/")).read_bytes()).hexdigest()==v["sha256"]
                for n,v in previous.items()
            )
            fresh_ok=all(not lab.joinpath(*n.split("/")).exists() for n in fresh)
        shell=verify_restored_shell(shell_snapshot,appdata=appdata,desktop=desktop,
                                   registry_values=lambda key,names:registry.read_key(key))
        if (len(previous)!=236 or len(fresh)!=22 or not old_ok or not fresh_ok
                or shell.get("verified") is not True):
            return {**denied,"reason":"POSTRESTORE_STATE_MISMATCH"}
        return {"state":"P9B_EXTERNAL_LAB_POSTVERIFY_MATCHED","verified":True,
                "old_files":236,"new_targets_absent":22,
                "shortcuts":5,"hkcu_keys":2,"inspection_only":True}
    except (OSError,ValueError,KeyError,TypeError):
        return {**denied,"reason":"POSTVERIFY_EXCEPTION"}


if __name__=="__main__":
    if len(sys.argv)!=10:
        raise SystemExit(2)
    outcome=verify(lab=sys.argv[1],snapshot=sys.argv[2],
                   shell_snapshot=sys.argv[3],appdata=sys.argv[4],
                   desktop=sys.argv[5],registry_token=sys.argv[6],
                   snapshot_sha256=sys.argv[7],shell_sha256=sys.argv[8],
                   journal=sys.argv[9])
    print(json.dumps(outcome,sort_keys=True))
    raise SystemExit(0 if outcome["verified"] else 2)
