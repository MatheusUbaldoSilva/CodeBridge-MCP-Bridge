"""Build and verify an OFFLINE-only MCP P9-B overlay and rollback bundle.

The bundle builder NEVER changes installed CodeBridge files or restarts MCP.
It packages seven reviewed source modules and byte-exact previous versions,
including nonexistence markers for new modules.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZIP_DEFLATED

OVERLAY_FILES = (
    "author_mcp/mcp_server.py",
    "rag/runtime/incremental_job_queue.py",
    "rag/runtime/incremental_supervisor_lock.py",
    "rag/runtime/incremental_supervisor_fence.py",
    "rag/runtime/incremental_scheduler_public_pointer.py",
    "rag/runtime/incremental_installed_queue_bootstrap_preflight.py",
    "rag/runtime/incremental_authorized_queue_bootstrap.py",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_bounded(path: Path, *, limit: int = 2_000_000) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("UNTRUSTED_MCP_PACKAGE_FILE")
    return path.read_bytes()


def stage_mcp_bootstrap_overlay(source_root: Path, installed_root: Path, output: Path) -> dict:
    src = Path(source_root).resolve()
    installed = Path(installed_root).resolve()
    bundle = Path(output).absolute()
    if (not (src / ".git").is_dir() or not installed.is_dir()
            or bundle.exists() or bundle.is_symlink()
            or not bundle.parent.is_dir()
            or bundle.is_relative_to(src) or bundle.is_relative_to(installed)
            or installed == src):
        return {"state": "OVERLAY_STAGE_BLOCKED", "created": False}
    try:
        commit = subprocess.run(
            ["git", "-C", str(src), "rev-parse", "HEAD"],
            capture_output=True, check=True, timeout=10, text=True,
        ).stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            raise ValueError("GIT_SOURCE_REVISION_MISSING")
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"state": "OVERLAY_STAGE_BLOCKED", "created": False}
    receipt = {
        "schema_version": 1, "artifact_type": "P9B_MCP_OFFLINE_OVERLAY",
        "installed": False, "restart_performed": False,
        "queue_bootstrapped": False, "public_index_changed": False,
        "source_root": str(src), "installed_root": str(installed),
        "git_commit": commit,
        "files": {},
    }
    blobs: dict[str, bytes] = {}
    try:
        for relative in OVERLAY_FILES:
            parts = PurePosixPath(relative).parts
            if ".." in parts or len(parts) < 2:
                raise ValueError("INVALID_OVERLAY_FILE")
            new = src.joinpath(*parts)
            target = installed.joinpath(*parts)
            if target.is_symlink() or target.parent.is_symlink():
                raise ValueError("SYMLINKED_INSTALLED_TARGET")
            incoming = _read_bounded(new)
            committed = subprocess.run(
                ["git", "-C", str(src), "show", f"{commit}:{relative}"],
                capture_output=True, check=True, timeout=10,
            ).stdout
            if committed != incoming:
                raise ValueError("UNCOMMITTED_OVERLAY_SOURCE")
            previous = _read_bounded(target) if target.exists() else None
            if relative in ("author_mcp/mcp_server.py", "rag/runtime/incremental_job_queue.py") and previous is None:
                raise ValueError("INSTALLED_MCP_BASELINE_MISSING")
            receipt["files"][relative] = {
                "source_sha256": _sha(incoming),
                "installed_sha256": _sha(previous) if previous is not None else None,
                "installed_existed": previous is not None,
            }
            blobs["new/" + relative] = incoming
            if previous is not None:
                blobs["old/" + relative] = previous
        raw_manifest = json.dumps(receipt, sort_keys=True, indent=2).encode("utf-8")
        with bundle.open("xb") as stream:
            with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
                archive.writestr("receipt.json", raw_manifest)
                for name, payload in sorted(blobs.items()):
                    archive.writestr(name, payload)
        return {
            "state": "OFFLINE_OVERLAY_STAGED", "created": True,
            "path": str(bundle), "file_count": len(OVERLAY_FILES),
            "archive_sha256": _sha(bundle.read_bytes()),
            "installed_modified": False, "queue_bootstrapped": False,
        }
    except (OSError, ValueError, subprocess.SubprocessError):
        if bundle.exists():
            bundle.unlink()
        return {"state": "OVERLAY_STAGE_BLOCKED", "created": False}


def verify_mcp_bootstrap_overlay(archive_path: Path, installed_root: Path) -> dict:
    output = {"state": "OVERLAY_UNVERIFIED", "valid": False, "installed_modified": False}
    archive_path = Path(archive_path)
    installed = Path(installed_root).resolve()
    if not archive_path.is_file() or archive_path.is_symlink():
        return output
    try:
        with ZipFile(archive_path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or "receipt.json" not in names:
                return output
            if (sum(info.file_size for info in archive.infolist()) > 32_000_000
                    or archive.getinfo("receipt.json").file_size > 100_000):
                return output
            receipt = json.loads(archive.read("receipt.json"))
            if (receipt.get("schema_version") != 1
                    or receipt.get("artifact_type") != "P9B_MCP_OFFLINE_OVERLAY"
                    or receipt.get("installed") is not False
                    or set(receipt.get("files", {})) != set(OVERLAY_FILES)
                    or Path(receipt["installed_root"]).resolve() != installed
                    or re.fullmatch(r"[0-9a-f]{40}",
                                    str(receipt.get("git_commit", ""))) is None):
                return output
            expected = {"receipt.json"}
            for rel, entry in receipt["files"].items():
                new_name = "new/" + rel
                expected.add(new_name)
                if _sha(archive.read(new_name)) != entry["source_sha256"]:
                    return output
                target = installed.joinpath(*PurePosixPath(rel).parts)
                if target.is_symlink() or target.parent.is_symlink():
                    return output
                if entry["installed_existed"]:
                    old_name = "old/" + rel
                    expected.add(old_name)
                    previous = archive.read(old_name)
                    if (_sha(previous) != entry["installed_sha256"]
                            or _sha(_read_bounded(target)) != entry["installed_sha256"]):
                        return output
                elif target.exists():
                    return output
            if set(names) != expected:
                return output
        return {"state": "OVERLAY_VERIFIED_AND_NOT_INSTALLED",
                "valid": True, "installed_modified": False,
                "file_count": len(OVERLAY_FILES)}
    except (OSError, ValueError, KeyError, TypeError):
        return output
