"""Read-only inventory of NSIS-owned Windows registry keys and shortcuts.

Only app-specific HKCU keys and the five NSIS-defined links are in
scope. This is evidence, NOT a rollback implementation.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

APP_KEYS=(r"Software\CodeBridge",
          r"Software\Microsoft\Windows\CurrentVersion\Uninstall\CodeBridge")
MENU_LINKS=("CodeBridge.lnk","Configurar CodeBridge.lnk",
            "Extens\u00e3o ChatGPT Timer.lnk","Atualizar CodeBridge.lnk")
DESKTOP_LINK="CodeBridge 2.0 - MCP Bridge.lnk"


def inspect_shell_scope(*, appdata, desktop, registry_query=None):
    outcome={"state":"SHELL_SCOPE_UNVERIFIED", "read_only":True,
             "backup_created":False,"restore_performed":False}
    appdata=Path(appdata)
    desktop=Path(desktop)
    if registry_query is None:
        try:
            import winreg
        except ImportError:
            return {**outcome,"reason":"WINDOWS_REGISTRY_UNAVAILABLE"}
        def registry_query(key):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as registry:
                    count=winreg.QueryInfoKey(registry)[1]
                    return {"exists":True,
                            "value_names":[winreg.EnumValue(registry,n)[0]
                                           for n in range(count)]}
            except FileNotFoundError:
                return {"exists":False,"value_names":[]}
    try:
        keys={name:registry_query(name) for name in APP_KEYS}
        menu=appdata/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
        links=[menu/n for n in MENU_LINKS]+[desktop/DESKTOP_LINK]
        recorded=[]
        for link in links:
            if link.is_symlink():
                return {**outcome,"reason":"SYMLINKED_SHELL_SHORTCUT"}
            if link.is_file():
                data=link.read_bytes()
                recorded.append({"name":link.name,"exists":True,
                                 "bytes":len(data),
                                 "sha256":hashlib.sha256(data).hexdigest()})
            elif link.exists():
                return {**outcome,"reason":"UNEXPECTED_SHELL_TARGET"}
            else:
                recorded.append({"name":link.name,"exists":False})
        return {**outcome,"state":"SHELL_SCOPE_OBSERVED_ONLY",
                "registry_keys":keys,"shortcuts":recorded,
                "requires_registry_shortcut_restore_proof":True}
    except (OSError,TypeError,ValueError):
        return {**outcome,"reason":"SHELL_SCOPE_ENUMERATION_FAILED"}
