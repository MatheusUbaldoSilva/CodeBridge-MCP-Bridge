"""Read-only post-update MCP tool registration check (never starts an MCP listener).

This probe verifies the installed Python surface after a supervised update.
Import runs in a separate Python process with bytecode disabled; it never
enqueues jobs or calls the mutating bootstrap mode.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


_PROBE_SCRIPT = r'''
import asyncio
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "author_mcp"))
import mcp_server
from rag.runtime.incremental_authorized_queue_bootstrap import bootstrap_installed_queue

async def check():
    tools = await mcp_server.mcp.list_tools()
    found = [t for t in tools if t.name == "codebridge_rag_queue_bootstrap"]
    if len(found) != 1:
        raise RuntimeError("BOOTSTRAP_TOOL_NOT_REGISTERED")
    schema = found[0].input_schema.get("properties", {})
    if (schema.get("execute", {}).get("default") is not False
            or "confirmation" not in schema
            or "operator_approved" not in schema
            or "expected_generation" not in schema):
        raise RuntimeError("BOOTSTRAP_TOOL_SCHEMA_NOT_SAFE")
    preview = bootstrap_installed_queue(execute=False)
    print(json.dumps({
        "state": "POSTUPDATE_MCP_TOOL_OBSERVED",
        "registered": True,
        "execute_default": False,
        "preview_state": preview["state"],
        "public_generation": preview.get("public_generation"),
        "bootstrap_executed": preview["executed"],
        "safe_to_publish": preview["safe_to_publish"],
        "registered_count": len(found),
    }, sort_keys=True))

asyncio.run(check())
'''


def inspect_postupdate_mcp_tool(installed_root: Path, *,
                                expected_generation: str,
                                timeout_seconds: int = 30) -> dict:
    blocked = {
        "state": "POSTUPDATE_MCP_TOOL_UNVERIFIED",
        "verified": False,
        "installed_modified": False,
        "mcp_service_started": False,
        "job_queue_initialized": False,
        "scheduler_started": False,
        "deployment_authorized": False,
    }
    root = Path(installed_root).resolve()
    required = (
        root / "runtime" / "python" / "python.exe",
        root / "author_mcp" / "mcp_server.py",
        root / "rag" / "runtime" / "incremental_authorized_queue_bootstrap.py",
    )
    if (not root.is_dir() or not isinstance(expected_generation, str)
            or any(not p.is_file() or p.is_symlink() for p in required)):
        return {**blocked, "reason": "MCP_TOOL_SOURCE_NOT_INSTALLED"}
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 60:
        return {**blocked, "reason": "INVALID_PROBE_TIMEOUT"}
    try:
        # Running from a scratch working directory avoids accidental local
        # outputs inside the installation. -B prevents Python bytecode writes.
        with TemporaryDirectory(prefix="codebridge_p9b_postupdate_tool_") as temp:
            child = subprocess.run(
                [str(required[0]), "-B", "-c", _PROBE_SCRIPT, str(root)],
                cwd=temp, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True, text=True, timeout=timeout_seconds,
                check=False,
            )
        if child.returncode != 0:
            return {**blocked, "reason": "MCP_TOOL_PROCESS_FAILED",
                    "exit_code": child.returncode,
                    "error_hint": child.stderr[-250:]}
        value = json.loads(child.stdout.strip())
        if (not isinstance(value,dict)
                or value.get("state") != "POSTUPDATE_MCP_TOOL_OBSERVED"
                or value.get("registered") is not True
                or value.get("execute_default") is not False
                or value.get("bootstrap_executed") is not False
                or value.get("safe_to_publish") is not False
                or value.get("public_generation") != expected_generation
                or value.get("preview_state") != "BOOTSTRAP_PLAN_ONLY"
                or value.get("registered_count") != 1):
            return {**blocked, "reason": "MCP_TOOL_CONTRACT_UNVERIFIED",
                    "preview_state": value.get("preview_state") if isinstance(value,dict) else None}
        return {**blocked, "state": "POSTUPDATE_MCP_TOOL_READONLY_VERIFIED",
                "verified": True,
                "public_generation": value["public_generation"],
                "preview_state": value["preview_state"],
                "registered_count": 1}
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        return {**blocked, "reason": "POSTUPDATE_TOOL_PROBE_FAILED"}


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", required=True, type=Path)
    parser.add_argument("--generation", required=True)
    arguments = parser.parse_args(argv)
    report = inspect_postupdate_mcp_tool(
        arguments.install_root, expected_generation=arguments.generation,
    )
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
