"""Durable preimage of exactly five CodeBridge shortcuts and two HKCU keys.

Requires injected registry reader. No live mutation. The preimage is bound
to a unique new archive and persisted before any restore transaction.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

from installer.rag_p9b_windows_shell_scope import APP_KEYS, MENU_LINKS, DESKTOP_LINK
from installer.rag_p9b_shell_snapshot import _ALLOWED_REGISTRY_NAMES


def create_crash_preimage(*, appdata, desktop, registry, output):
    base={"state":"PREIMAGE_REFUSED","created":False,"installed_modified":False}
    target=Path(output)
    if (target.exists() or target.is_symlink() or not target.parent.is_dir()
            or target.parent.is_symlink()):
        return {**base,"reason":"UNSAFE_OUTPUT"}
    paths=[Path(appdata)/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"/n
           for n in MENU_LINKS]+[Path(desktop)/DESKTOP_LINK]
    links=[]
    blobs={}
    reg={}
    try:
        for i,path in enumerate(paths):
            if path.is_symlink() or (path.exists() and not path.is_file()):
                return {**base,"reason":"SHORTCUT_UNSAFE"}
            data=path.read_bytes() if path.is_file() else None
            if data is not None and len(data)>65536:
                return {**base,"reason":"SHORTCUT_OVERSIZED"}
            links.append({"slot":i,"name":path.name,"exists":data is not None,
                          "sha256":hashlib.sha256(data).hexdigest() if data is not None else None})
            if data is not None:
                blobs[f"links/{i}.bin"]=data
        for key,names in zip(APP_KEYS,_ALLOWED_REGISTRY_NAMES):
            entry=registry.read_key(key)
            if (not isinstance(entry,dict) or not isinstance(entry.get("exists"),bool)
                    or not isinstance(entry.get("values"),dict)
                    or set(entry["values"])-set(names)):
                return {**base,"reason":"REGISTRY_SCOPE_UNVERIFIED"}
            if not entry["exists"] and entry["values"]:
                return {**base,"reason":"REGISTRY_SCOPE_UNVERIFIED"}
            for value in entry["values"].values():
                if (value.get("type") not in (1,4)
                        or isinstance(value.get("value"),bool)
                        or not isinstance(value.get("value"),str if value.get("type")==1 else int)):
                    return {**base,"reason":"REGISTRY_VALUE_UNVERIFIED"}
            reg[key]=entry
        manifest={"schema":1,"purpose":"P9B_CRASH_PREIMAGE","registry":reg,"links":links}
        with target.open("xb") as stream:
            with ZipFile(stream,"w",ZIP_STORED) as archive:
                archive.writestr("manifest.json",json.dumps(manifest,sort_keys=True))
                for name,data in blobs.items():
                    archive.writestr(name,data)
            stream.flush()
            os.fsync(stream.fileno())
        return {**base,"state":"CRASH_PREIMAGE_DURABLE","created":True,
                "sha256":hashlib.sha256(target.read_bytes()).hexdigest()}
    except (OSError,ValueError,TypeError,KeyError) as exc:
        return {**base,"reason":"PREIMAGE_PERSISTENCE_FAILED",
                "partial_file_present":target.exists()}


def verify_crash_preimage(path, expected_sha256):
    base={"state":"PREIMAGE_UNVERIFIED","verified":False,"read_only":True}
    source=Path(path)
    expected=str(expected_sha256).lower()
    if (len(expected)!=64 or any(c not in "0123456789abcdef" for c in expected)
            or not source.is_file() or source.is_symlink()):
        return {**base,"reason":"IDENTITY_INVALID"}
    try:
        if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
            return {**base,"reason":"SHA256_MISMATCH"}
        with ZipFile(source) as archive:
            names=archive.namelist()
            if len(names)!=len(set(names)):return {**base,"reason":"DUPLICATE_MEMBERS"}
            if archive.getinfo("manifest.json").file_size > 16384:
                return {**base,"reason":"MANIFEST_OVERSIZED"}
            meta=json.loads(archive.read("manifest.json"))
            if (meta.get("schema")!=1 or meta.get("purpose")!="P9B_CRASH_PREIMAGE"
                    or set(meta.get("registry",{}))!=set(APP_KEYS)
                    or len(meta.get("links",[]))!=5):
                return {**base,"reason":"SCHEMA_INVALID"}
            expected_members={"manifest.json"}
            expected_names=list(MENU_LINKS)+[DESKTOP_LINK]
            for i,item in enumerate(meta["links"]):
                if item.get("slot")!=i or item.get("name")!=expected_names[i] or not isinstance(item.get("exists"),bool):
                    return {**base,"reason":"LINK_SCOPE_INVALID"}
                if item["exists"]:
                    member=f"links/{i}.bin"
                    expected_members.add(member)
                    if archive.getinfo(member).file_size>65536:
                        return {**base,"reason":"OVERSIZED"}
                    if hashlib.sha256(archive.read(member)).hexdigest()!=item.get("sha256"):
                        return {**base,"reason":"LINK_HASH_INVALID"}
            if set(names)!=expected_members:return {**base,"reason":"EXTRA_MEMBERS"}
            for key,allowed in zip(APP_KEYS,_ALLOWED_REGISTRY_NAMES):
                entry=meta["registry"][key]
                if (not isinstance(entry,dict)
                        or not isinstance(entry.get("exists"),bool)
                        or not isinstance(entry.get("values"),dict)
                        or set(entry["values"])-set(allowed)
                        or (not entry["exists"] and entry["values"])):
                    return {**base,"reason":"REGISTRY_SCOPE_INVALID"}
                for value in entry["values"].values():
                    if (value.get("type") not in (1,4)
                        or isinstance(value.get("value"),bool)
                        or not isinstance(value.get("value"),str if value.get("type")==1 else int)):
                        return {**base,"reason":"REGISTRY_TYPE_INVALID"}
        return {**base,"state":"CRASH_PREIMAGE_VERIFIED","verified":True}
    except (OSError,ValueError,TypeError,KeyError,IndexError):
        return {**base,"reason":"PREIMAGE_READ_FAILED"}
