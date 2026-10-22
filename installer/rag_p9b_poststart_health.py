"""Post-recovery local health proof. Does not imply public ChatGPT handshake."""
from __future__ import annotations
import importlib.util
from pathlib import Path


def check_local_poststart(installed:Path, *, probe=None):
    base=dict(state="POSTSTART_UNVERIFIED",verified=False,
              public_mcp_handshake_verified=False,
              installer_executed=False,read_only=True)
    root=Path(installed).resolve()
    if not (root/"app_rewrite"/"author_mcp_status.py").is_file():
        return {**base,"reason":"HEALTH_PROBE_SOURCE_MISSING"}
    try:
        if probe is None:
            source=root/"app_rewrite"/"author_mcp_status.py"
            spec=importlib.util.spec_from_file_location(
                "cb_poststart_installed_status",source)
            module=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            probe=module.AuthorMCPStatus().status
        health=probe()
    except Exception:
        return {**base,"reason":"HEALTH_PROBE_FAILED"}
    if (health.get("state")!="ONLINE"
            or health.get("adapter_online") is not True
            or health.get("mcp_online") is not True):
        return {**base,"reason":"LOCAL_MCP_NOT_READY",
                "health_state":health.get("state")}
    return {**base,"state":"LOCAL_ADAPTER_AND_MCP_READY",
            "verified":True,
            "public_mcp_handshake_verified":False,
            "requires_public_reconnect":True}
