"""Strictly scoped HKCU interface; no registry writes without explicit backend invocation.

Never touches secrets or arbitrary registry paths. No read/write occurs
at import; the constructor is inert until read_key or replace_key.
"""
from __future__ import annotations

from installer.rag_p9b_shell_snapshot import _ALLOWED_REGISTRY_NAMES
from installer.rag_p9b_windows_shell_scope import APP_KEYS


class ScopedHKCU:
    def __init__(self, winreg_module=None):
        if winreg_module is None:
            import winreg
            winreg_module=winreg
        self.winreg=winreg_module

    def _validate_scope(self,key):
        if key not in APP_KEYS:
            raise ValueError("REGISTRY_KEY_OUTSIDE_CODEBRIDGE_SCOPE")
        return _ALLOWED_REGISTRY_NAMES[APP_KEYS.index(key)]

    def read_key(self,key):
        wr=self.winreg
        names=self._validate_scope(key)
        try:
            with wr.OpenKey(wr.HKEY_CURRENT_USER,key) as handle:
                found={}
                for name in names:
                    try: value,kind=wr.QueryValueEx(handle,name)
                    except FileNotFoundError: continue
                    if (kind not in (wr.REG_SZ,wr.REG_DWORD)
                            or isinstance(value,bool)
                            or not isinstance(value,str if kind==wr.REG_SZ else int)):
                        raise ValueError("UNSUPPORTED_REGISTRY_TYPE")
                    found[name]={"type":kind,"value":value}
                return {"exists":True,"values":found}
        except FileNotFoundError:
            return {"exists":False,"values":{}}

    def replace_key(self,key,record):
        wr=self.winreg
        names=self._validate_scope(key)
        if (not isinstance(record,dict) or not isinstance(record.get("exists"),bool)
                or not isinstance(record.get("values"),dict)
                or set(record["values"])-set(names)
                or (not record["exists"] and record["values"])):
            raise ValueError("REGISTRY_RESTORE_RECORD_INVALID")
        for item in record["values"].values():
            if (not isinstance(item,dict)
                    or item.get("type") not in (wr.REG_SZ,wr.REG_DWORD)
                    or isinstance(item.get("value"),bool)
                    or not isinstance(item.get("value"),str if item.get("type")==wr.REG_SZ else int)):
                raise ValueError("REGISTRY_RESTORE_TYPE_INVALID")
        if not record["exists"]:
            try:
                with wr.OpenKey(wr.HKEY_CURRENT_USER,key) as handle:
                    subkeys,values,_=wr.QueryInfoKey(handle)
                    if subkeys:
                        raise ValueError("REGISTRY_KEY_HAS_UNEXPECTED_SUBKEYS")
                    observed={wr.EnumValue(handle,i)[0] for i in range(values)}
                    if observed-set(names):
                        raise ValueError("REGISTRY_KEY_HAS_FOREIGN_VALUES")
                wr.DeleteKey(wr.HKEY_CURRENT_USER,key)
            except FileNotFoundError:
                pass
            return
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER,key,0,wr.KEY_READ|wr.KEY_WRITE) as handle:
            for name in names:
                if name not in record["values"]:
                    try:wr.DeleteValue(handle,name)
                    except FileNotFoundError:pass
                else:
                    value=record["values"][name]
                    wr.SetValueEx(handle,name,0,value["type"],value["value"])
