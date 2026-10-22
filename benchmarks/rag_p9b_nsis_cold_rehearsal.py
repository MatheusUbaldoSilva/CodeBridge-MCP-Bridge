"""P9-B cold installer rehearsal: never invokes NSIS or touches installed files.

Verifies Git provenance and byte-exact pre-update backup, extracts a release
into a brand-new disposable directory, loads the *staged* MCP as a separate
Python subprocess, and exercises only the non-mutating queue bootstrap preview.
This is evidence of code compatibility, NOT of live service reconnection.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from installer.rag_p9b_clean_release_audit import audit_p9b_nsis_payload
from installer.rag_p9b_installer_rollback_scope import (
    inspect_installer_snapshot_baseline,
    payload_file_list,
    verify_installer_rollback_snapshot,
)
from installer.rag_p9b_postupdate_mcp_tool_probe import _PROBE_SCRIPT


_COLD_RAG_STATUS_SUFFIX = r"""
# Executed after the registered-tool check, in the SAME disposable process.
status = mcp_server.codebridge_rag_status()
projects = [x for x in status.projects if x.get("project_id") == "codebridge"]
print(json.dumps({
    "state": "STAGED_MCP_RAG_STATUS_OBSERVED",
    "operation_ok": bool(status.operation_ok),
    "index_state": status.index.get("state"),
    "generation": status.index.get("generation"),
    "document_count": (projects[0].get("document_count") if len(projects) == 1 else None),
    "chunk_count": (projects[0].get("chunk_count") if len(projects) == 1 else None),
}, sort_keys=True))
"""

_COLD_MCP_DISPATCH_SUFFIX = r"""
# Dispatches through FastMCP's real tool-call handler with EMPTY arguments.
# This must use default execute=False; never pass operator approval or a token.
async def call_default():
    result = await mcp_server.mcp.call_tool("codebridge_rag_queue_bootstrap", {})
    response = result.structured_content or {}
    details = response.get("details") or {}
    print(json.dumps({
        "state": "STAGED_MCP_TOOL_DISPATCH_OBSERVED",
        "operation_ok": response.get("operation_ok"),
        "bootstrap_state": response.get("state"),
        "executed": response.get("executed"),
        "safe_to_publish": response.get("safe_to_publish"),
        "directory_created": details.get("directory_created"),
        "queue_created": details.get("queue_initialized"),
    }, sort_keys=True))

asyncio.run(call_default())
"""




def rehearse_cold_nsis_bootstrap(
    *, repo: Path, installed: Path, installer: Path, snapshot: Path,
    seven_zip: Path, expected_commit: str, expected_generation: str,
    expected_document_count: int = 211, expected_chunk_count: int = 8774,
) -> dict:
    base = {
        "state": "COLD_INSTALLER_REHEARSAL_BLOCKED",
        "verified": False,
        "installer_executed": False,
        "mcp_service_started": False,
        "installed_modified": False,
        "queue_initialized": False,
        "rollback_performed": False,
        "live_mcp_reconnected": False,
        "deployment_authorized": False,
    }
    repo = Path(repo).resolve()
    installed = Path(installed).resolve()
    installer = Path(installer)
    snapshot = Path(snapshot)
    seven_zip = Path(seven_zip)
    portable = installed / "runtime" / "python" / "python.exe"

    try:
        if (not portable.is_file() or portable.is_symlink()
                or not seven_zip.is_file()
                or not expected_generation.startswith("v1_delta_")
                or type(expected_document_count) is not int
                or type(expected_chunk_count) is not int
                or expected_document_count < 1 or expected_chunk_count < 1):
            return {**base, "reason": "PREREQUISITES_UNVERIFIED"}
        provenance = audit_p9b_nsis_payload(
            repo, installer, seven_zip, expected_commit=expected_commit,
        )
        if not provenance.get("verified"):
            return {**base, "reason": "SOURCE_PROVENANCE_FAILED"}
        backup = verify_installer_rollback_snapshot(snapshot, installed)
        if (not backup.get("verified")
                or backup.get("installer_sha256") != provenance.get("sha256")):
            return {**base, "reason": "BACKUP_IDENTITY_MISMATCH"}
        installed_before = inspect_installer_snapshot_baseline(snapshot, installed)
        if not installed_before.get("matches"):
            return {**base, "reason": "PREUPDATE_BASELINE_CHANGED"}
        # payload_file_list enforces approved paths and no rogue files.
        approved = payload_file_list(installer, seven_zip)
        with TemporaryDirectory(prefix="codebridge_p9b_cold_nsis_rehearsal_") as temp:
            stage = Path(temp) / "release"
            stage.mkdir()
            extract = subprocess.run(
                [str(seven_zip), "x", "-y", "-o" + str(stage), str(installer)],
                capture_output=True, text=True, timeout=100, check=False,
            )
            if extract.returncode:
                return {**base, "reason": "NSIS_PAYLOAD_EXTRACT_FAILED"}
            for relative in approved:
                staged = stage.joinpath(*relative.split("/"))
                if not staged.is_file() or staged.is_symlink():
                    return {**base, "reason": "STAGED_RELEASE_INCOMPLETE",
                            "missing": relative}
            # -B suppresses bytecode writes, the script checks execute=False.
            check = subprocess.run(
                [str(portable), "-B", "-c",
                 _PROBE_SCRIPT + "\n" + _COLD_RAG_STATUS_SUFFIX
                 + "\n" + _COLD_MCP_DISPATCH_SUFFIX, str(stage)],
                cwd=temp,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True, text=True, timeout=35, check=False,
            )
            if check.returncode:
                return {**base, "reason": "STAGED_MCP_IMPORT_FAILED",
                        "exit_code": check.returncode,
                        "stderr_hint": check.stderr[-250:]}
            outputs = check.stdout.strip().splitlines()
            if len(outputs) != 3:
                return {**base, "reason": "STAGED_MCP_OUTPUT_UNEXPECTED"}
            report = json.loads(outputs[0])
            status = json.loads(outputs[1])
            dispatch = json.loads(outputs[2])
            if (report.get("state") != "POSTUPDATE_MCP_TOOL_OBSERVED"
                    or report.get("registered") is not True
                    or report.get("registered_count") != 1
                    or report.get("execute_default") is not False
                    or report.get("bootstrap_executed") is not False
                    or report.get("safe_to_publish") is not False
                    or report.get("public_generation") != expected_generation
                    or report.get("preview_state") != "BOOTSTRAP_PLAN_ONLY"):
                return {**base, "reason": "STAGED_MCP_PREVIEW_UNEXPECTED"}
            if (status.get("state") != "STAGED_MCP_RAG_STATUS_OBSERVED"
                    or status.get("operation_ok") is not True
                    or status.get("index_state") != "READY"
                    or status.get("generation") != expected_generation
                    or status.get("document_count") != expected_document_count
                    or status.get("chunk_count") != expected_chunk_count):
                return {**base, "reason": "STAGED_PUBLIC_RAG_STATUS_UNVERIFIED"}
            if (dispatch.get("state") != "STAGED_MCP_TOOL_DISPATCH_OBSERVED"
                    or dispatch.get("operation_ok") is not True
                    or dispatch.get("bootstrap_state") != "BOOTSTRAP_PLAN_ONLY"
                    or dispatch.get("executed") is not False
                    or dispatch.get("safe_to_publish") is not False
                    or dispatch.get("directory_created") is not False
                    or dispatch.get("queue_created") is True):
                return {**base, "reason": "STAGED_MCP_DISPATCH_NOT_READONLY"}
        installed_after = inspect_installer_snapshot_baseline(snapshot, installed)
        if not installed_after.get("matches"):
            return {**base, "reason": "INSTALLED_CHANGED_DURING_REHEARSAL"}
        return {**base,
                "state": "COLD_INSTALLER_READONLY_REHEARSAL_PASS",
                "verified": True,
                "staged_python_files": sum(
                    name.lower().endswith(".py") for name in approved
                ),
                "payload_targets": len(approved),
                "public_generation": expected_generation,
                "public_documents": expected_document_count,
                "public_chunks": expected_chunk_count,
                "mcp_tool_registered_offline": True,
                "mcp_tool_dispatched_readonly": True,
                "public_index_readonly_observed": True}
    except (OSError, ValueError, TypeError, KeyError,
            subprocess.TimeoutExpired, subprocess.SubprocessError):
        return {**base, "reason": "COLD_REHEARSAL_FAILED"}


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--installed", required=True, type=Path)
    parser.add_argument("--installer", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--seven-zip", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--generation", required=True)
    parser.add_argument("--expected-documents", type=int, default=211)
    parser.add_argument("--expected-chunks", type=int, default=8774)
    args = parser.parse_args(argv)
    data = rehearse_cold_nsis_bootstrap(
        repo=args.repo, installed=args.installed,
        installer=args.installer, snapshot=args.snapshot,
        seven_zip=args.seven_zip,
        expected_commit=args.commit, expected_generation=args.generation,
        expected_document_count=args.expected_documents,
        expected_chunk_count=args.expected_chunks,
    )
    print(json.dumps(data, sort_keys=True))
    return 0 if data["verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
