"""Read-only restart prerequisite inventory for supervised CodeBridge cutover."""
from __future__ import annotations

from pathlib import Path

REQUIRED = (
    "app_rewrite/main.py",
    "app_rewrite/runtime.py",
    "author_mcp/mcp_server.py",
    "author_mcp/adapter_server.py",
    "tools/tunnel-client.exe",
    "runtime/python/python.exe",
    "runtime/python/pythonw.exe",
)


def inspect_restart_prerequisites(installed: Path) -> dict:
    root=Path(installed).resolve()
    result=dict(state="RESTART_UNVERIFIED",read_only=True,
                restarted=False,installer_executed=False,
                safe_to_update=False)
    if not root.is_dir():
        return {**result,"reason":"INSTALL_ROOT_NOT_FOUND"}
    found=[]
    missing=[]
    untrusted=[]
    for rel in REQUIRED:
        path=root.joinpath(*Path(rel).parts)
        if path.is_symlink() or any(p.is_symlink() for p in
            path.parents if p == root or root in p.parents):
            untrusted.append(rel)
        elif path.is_file() and path.stat().st_size > 0:
            found.append(rel)
        else:
            missing.append(rel)
    if untrusted:
        return {**result,"reason":"SYMLINKED_RESTART_PATH",
                "untrusted":untrusted}
    if missing:
        return {**result,"reason":"RESTART_COMPONENT_MISSING",
                "present":found,"missing":missing}
    return {**result,"state":"RESTART_FILES_OBSERVED_ONLY",
            "present":found,
            "independent_recovery_channel_still_required":True,
            "poststart_handshake_still_required":True}
