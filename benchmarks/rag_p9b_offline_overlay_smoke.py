"""End-to-end dry-run the reviewed offline MCP overlay under installed Python.

This module is read-only against installed CodeBridge; it never stops/restarts
services, initializes a production queue or copies overlay into installed root.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from installer.rag_p9b_mcp_overlay import (
    OVERLAY_FILES, verify_mcp_bootstrap_overlay,
)


def smoke_verified_overlay(archive_path: Path, installed_root: Path) -> dict:
    installed = Path(installed_root).resolve()
    bundle = Path(archive_path)
    checked = verify_mcp_bootstrap_overlay(bundle, installed)
    base = {"installed_modified": False, "mcp_restarted": False,
            "queue_initialized": False, "safe_to_activate": False}
    if not checked["valid"]:
        return {**base, "state": "OVERLAY_UNVERIFIED"}
    portable = installed / "runtime" / "python" / "python.exe"
    if not portable.is_file() or portable.is_symlink():
        return {**base, "state": "PORTABLE_PYTHON_UNAVAILABLE"}
    try:
        with TemporaryDirectory(prefix="codebridge_p9b_overlay_smoke_") as temp:
            folder = Path(temp)
            for relative in ("rag", "author_mcp"):
                src = installed / relative
                if src.is_symlink():
                    return {**base, "state": "UNTRUSTED_INSTALLED_RUNTIME"}
                shutil.copytree(
                    src, folder / relative,
                    ignore=shutil.ignore_patterns(
                        "__pycache__", "*.pyc", ".venv", "*.log",
                        "*.sqlite*", "*.db", "*.gguf", "*.bin", "qdrant",
                    ),
                )
            with ZipFile(bundle) as archive:
                for relative in OVERLAY_FILES:
                    dest = folder / relative
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(archive.read("new/" + relative))
            script = r'''
import asyncio, json, sys
from pathlib import Path
staged = Path(sys.argv[1])
sys.path.insert(0, str(staged))
sys.path.insert(0, str(staged / "author_mcp"))
from rag.runtime.incremental_authorized_queue_bootstrap import bootstrap_installed_queue
import mcp_server
async def probe():
    tools = await mcp_server.mcp.list_tools()
    candidates = [tool for tool in tools if tool.name == "codebridge_rag_queue_bootstrap"]
    assert len(candidates) == 1
    assert candidates[0].input_schema["properties"]["execute"]["default"] is False
    report = bootstrap_installed_queue(execute=False)
    assert report["state"] == "BOOTSTRAP_PLAN_ONLY"
    assert report["executed"] is False
    assert report["safe_to_publish"] is False
    print(json.dumps({
        "state":"OFFLINE_MCP_OVERLAY_SMOKE_PASS",
        "registered_tool": candidates[0].name,
        "tool_count":len(tools), "preview_state":report["state"],
        "public_generation":report.get("public_generation"),
    }, sort_keys=True))
asyncio.run(probe())
'''
            result = subprocess.run(
                [str(portable), "-c", script, str(folder)],
                cwd=str(folder), capture_output=True, text=True,
                timeout=35, check=False,
            )
            if result.returncode != 0:
                return {**base, "state": "STAGED_MCP_IMPORT_FAILED",
                        "exit_code": result.returncode,
                        "stderr_tail": result.stderr[-450:]}
            payload = json.loads(result.stdout.strip())
            if payload.get("state") != "OFFLINE_MCP_OVERLAY_SMOKE_PASS":
                return {**base, "state": "STAGED_MCP_UNEXPECTED_RESPONSE"}
            return {**base, **payload}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {**base, "state": "STAGED_MCP_IMPORT_FAILED"}
