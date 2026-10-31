"""F-7: compare live function bytecode with on-disk, non-executed source.

A disk/bytecode match is a diagnostic only: disk can be mutable and the
installed GUI process cannot be inspected without its own trusted channel.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
from types import CodeType, FunctionType

_MAX_SOURCE_BYTES=262144

def match_loaded_top_level_function_dev(function:object,source_path:Path,
                                       symbol:str)->dict:
    """Fail closed without importing/executing target modules or opening DBs."""
    result={
        "state":"DEV_LOADED_FUNCTION_SOURCE_UNVERIFIED",
        "source_sha256":None,
        "loaded_code_matches_disk":False,
        "source_read_only":True,
        "installed_gui_attested":False,
        "activation_authorized":False,
        "operational_use_allowed":False,
    }
    if (not isinstance(source_path,Path) or not source_path.is_absolute()
            or not isinstance(symbol,str) or not symbol.isidentifier()):
        raise ValueError("absolute source file and symbol required")
    if not isinstance(function,FunctionType) or function.__name__!=symbol:
        return result
    if source_path.is_symlink() or (hasattr(source_path,"is_junction")
                                   and source_path.is_junction()):
        return result
    try:
        pre=source_path.stat()
        if (not source_path.is_file() or pre.st_size>_MAX_SOURCE_BYTES
                or pre.st_size<1):
            return result
        # No exec/import of source. A changed source invalidates the receipt.
        raw=source_path.read_bytes()
        post=source_path.stat()
        if (len(raw)!=pre.st_size or (pre.st_size,pre.st_mtime_ns)!=
                (post.st_size,post.st_mtime_ns)):
            return result
        code=compile(raw,str(source_path),"exec",dont_inherit=True)
    except (OSError,SyntaxError,ValueError,UnicodeError):
        return result
    declared=[c for c in code.co_consts
              if isinstance(c,CodeType) and c.co_name==symbol]
    if len(declared)!=1:
        return result
    expected=declared[0]
    current=function.__code__
    if (current.co_filename!=str(source_path)
            or expected.co_filename!=str(source_path)
            or current!=expected):
        return result
    result.update(
        state="DEV_LOADED_FUNCTION_DISK_BYTECODE_MATCH",
        source_sha256=hashlib.sha256(raw).hexdigest(),
        loaded_code_matches_disk=True,
    )
    return result
