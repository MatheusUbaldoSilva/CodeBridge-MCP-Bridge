"""Constrained HKCU CodeBridge+shortcut snapshot, no production restore.

Captures exactly NSIS-written registry values and known shortcuts.
A future restore routine must be separately reviewed and rehearsed.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

from installer.rag_p9b_windows_shell_scope import (
    APP_KEYS, MENU_LINKS, DESKTOP_LINK,
)

_ALLOWED_REGISTRY_NAMES=(
    ("InstallDir","Version"),
    ("DisplayName","DisplayVersion","Publisher","InstallLocation",
     "DisplayIcon","UninstallString","NoModify","NoRepair"),
)


def snapshot_shell_state(*, appdata, desktop, snapshot, registry_values=None):
    base={"state":"SHELL_BACKUP_REFUSED","created":False,
          "installed_modified":False,"restore_performed":False}
    path=Path(snapshot)
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        return {**base,"reason":"TARGET_ALREADY_EXISTS_OR_PARENT_MISSING"}
    if registry_values is None:
        try:
            import winreg
        except ImportError:
            return {**base,"reason":"WINREG_UNAVAILABLE"}
        def registry_values(key, names):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as reg:
                    values={}
                    for name in names:
                        try:
                            value,kind=winreg.QueryValueEx(reg,name)
                        except FileNotFoundError:
                            continue
                        if kind not in (winreg.REG_SZ,winreg.REG_DWORD) or not isinstance(value,(str,int)):
                            raise ValueError("UNSUPPORTED_REGISTRY_VALUE")
                        values[name]={"type":kind,"value":value}
                    return {"exists":True,"values":values}
            except FileNotFoundError:
                return {"exists":False,"values":{}}
    paths=[Path(appdata)/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"/n
           for n in MENU_LINKS]
    paths.append(Path(desktop)/DESKTOP_LINK)
    try:
        keys={}
        for key,names in zip(APP_KEYS,_ALLOWED_REGISTRY_NAMES):
            result=registry_values(key,names)
            if not isinstance(result,dict) or not isinstance(result.get("exists"),bool):
                return {**base,"reason":"INVALID_REGISTRY_DATA"}
            values=result.get("values",{})
            if (not isinstance(values,dict) or set(values)-set(names)
                    or any(not isinstance(v,dict)
                           or v.get("type") not in (1,4)
                           or not isinstance(v.get("value"),(str,int))
                           for v in values.values())):
                return {**base,"reason":"UNEXPECTED_REGISTRY_VALUES"}
            keys[key]={"exists":result["exists"],"values":values}
        links=[]
        blobs={}
        for n,file in enumerate(paths):
            if file.is_symlink() or (file.exists() and not file.is_file()):
                return {**base,"reason":"UNTRUSTED_SHORTCUT_PATH"}
            item={"slot":n,"name":file.name,"exists":file.is_file()}
            if file.is_file():
                data=file.read_bytes()
                if len(data)>65536:
                    return {**base,"reason":"OVERSIZED_SHORTCUT"}
                member=f"links/{n}.bin"
                blobs[member]=data
                item.update({"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)})
            links.append(item)
        manifest={"schema":1,"state":"P9B_SHELL_BACKUP","registry":keys,
                  "shortcuts":links}
        with path.open("xb") as stream:
            with ZipFile(stream,"w",ZIP_DEFLATED) as zipfile:
                zipfile.writestr("manifest.json",json.dumps(manifest,sort_keys=True))
                for name,data in blobs.items():
                    zipfile.writestr(name,data)
        return {**base,"state":"SHELL_BACKUP_CREATED","created":True,
                "registry_keys":len(keys),"shortcuts":len(links),
                "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    except (OSError,ValueError,TypeError):
        return {**base,"reason":"SHELL_BACKUP_EXCEPTION",
                "partial_file_present":path.exists()}


def verify_shell_snapshot(snapshot):
    result={"state":"SHELL_BACKUP_UNVERIFIED","verified":False,
            "read_only":True,"restore_performed":False}
    try:
        with ZipFile(snapshot) as z:
            names=z.namelist()
            if len(names)!=len(set(names)) or "manifest.json" not in names:
                return result
            meta=json.loads(z.read("manifest.json"))
            if (meta.get("schema")!=1 or meta.get("state")!="P9B_SHELL_BACKUP"
                    or not isinstance(meta.get("registry"),dict)
                    or set(meta["registry"])!=set(APP_KEYS)
                    or not isinstance(meta.get("shortcuts"),list)
                    or len(meta["shortcuts"])!=5):
                return result
            for key,allowed in zip(APP_KEYS,_ALLOWED_REGISTRY_NAMES):
                entry=meta["registry"][key]
                if (not isinstance(entry,dict)
                        or not isinstance(entry.get("exists"),bool)
                        or not isinstance(entry.get("values"),dict)
                        or set(entry["values"])-set(allowed)):
                    return result
                for v in entry["values"].values():
                    if (not isinstance(v,dict)
                            or v.get("type") not in (1,4)
                            or isinstance(v.get("value"),bool)
                            or not isinstance(v.get("value"),str if v.get("type")==1 else int)):
                        return result
            expected_links=["CodeBridge.lnk","Configurar CodeBridge.lnk",
                            "Extens\u00e3o ChatGPT Timer.lnk","Atualizar CodeBridge.lnk",
                            DESKTOP_LINK]
            expected_members={"manifest.json"}
            for index,item in enumerate(meta["shortcuts"]):
                if (not isinstance(item,dict) or item.get("slot")!=index
                        or item.get("name")!=expected_links[index]
                        or not isinstance(item.get("exists"),bool)):
                    return result
                if item["exists"]:
                    member=f"links/{index}.bin"
                    expected_members.add(member)
                    if z.getinfo(member).file_size > 65536:
                        return result
                    payload=z.read(member)
                    if (not 0<len(payload)<=65536
                            or item.get("bytes")!=len(payload)
                            or hashlib.sha256(payload).hexdigest()!=item.get("sha256")):
                        return result
            if set(names)!=expected_members:
                return result
            return {**result,"state":"SHELL_BACKUP_VERIFIED","verified":True,
                    "shortcut_count":5,"registry_keys":len(APP_KEYS)}
    except (OSError,ValueError,KeyError,TypeError,BadZipFile):
        return result
