"""Read-only post-restore comparison to an exact P9-B shell snapshot."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from installer.rag_p9b_shell_snapshot import verify_shell_snapshot, _ALLOWED_REGISTRY_NAMES
from installer.rag_p9b_windows_shell_scope import APP_KEYS, MENU_LINKS, DESKTOP_LINK


def verify_restored_shell(snapshot, *, appdata, desktop, registry_values=None):
    result={"state":"SHELL_POSTRESTORE_UNVERIFIED","verified":False,
            "registry_modified":False,"shortcuts_modified":False,
            "inspection_only":True}
    if not verify_shell_snapshot(snapshot).get("verified"):
        return {**result,"reason":"BACKUP_UNVERIFIED"}
    if registry_values is None:
        try:
            import winreg
        except ImportError:
            return {**result,"reason":"REGISTRY_UNAVAILABLE"}
        def registry_values(key,names):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as reg:
                    values={}
                    for name in names:
                        try: value,kind=winreg.QueryValueEx(reg,name)
                        except FileNotFoundError: continue
                        values[name]={"value":value,"type":kind}
                    return {"exists":True,"values":values}
            except FileNotFoundError:
                return {"exists":False,"values":{}}
    try:
        with ZipFile(snapshot) as z:
            manifest=json.loads(z.read("manifest.json"))
            for key,names in zip(APP_KEYS,_ALLOWED_REGISTRY_NAMES):
                actual=registry_values(key,names)
                if actual!=manifest["registry"][key]:
                    return {**result,"reason":"REGISTRY_BASELINE_MISMATCH",
                            "key":key}
            targets=[Path(appdata)/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"/n
                     for n in MENU_LINKS]+[Path(desktop)/DESKTOP_LINK]
            for slot,(target,item) in enumerate(zip(targets,manifest["shortcuts"])):
                if target.is_symlink() or (target.exists() and not target.is_file()):
                    return {**result,"reason":"SHORTCUT_PATH_CHANGED","slot":slot}
                if target.is_file()!=item["exists"]:
                    return {**result,"reason":"SHORTCUT_EXISTENCE_MISMATCH","slot":slot}
                if target.is_file():
                    if hashlib.sha256(target.read_bytes()).hexdigest()!=item["sha256"]:
                        return {**result,"reason":"SHORTCUT_BYTES_MISMATCH","slot":slot}
            return {**result,"state":"SHELL_POSTRESTORE_MATCHED","verified":True,
                    "registry_keys_checked":2,"shortcuts_checked":5}
    except (OSError,ValueError,KeyError,TypeError,BadZipFile):
        return {**result,"reason":"READ_ONLY_POSTVERIFY_FAILED"}
