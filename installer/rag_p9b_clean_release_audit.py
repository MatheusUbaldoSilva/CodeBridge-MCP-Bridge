"""Reproducible, read-only verification of a clean P9-B NSIS binary."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from installer.rag_p9b_mcp_overlay import OVERLAY_FILES


def audit_p9b_nsis_payload(repo: Path, installer: Path, seven_zip: Path,
                           *, expected_commit: str) -> dict:
    blocked = {"state": "P9B_NSIS_PAYLOAD_UNVERIFIED", "verified": False,
               "installer_executed": False, "installed_modified": False}
    if (re.fullmatch(r"[0-9a-f]{40}", expected_commit) is None
            or not Path(installer).is_file()
            or Path(installer).is_symlink() or not Path(seven_zip).is_file()):
        return blocked
    try:
        tracked_result = subprocess.run(
            ["git", "-C", str(repo), "ls-tree", "-r", "--name-only",
             expected_commit],
            capture_output=True, text=True, check=True, timeout=15,
        )
        tracked = set(tracked_result.stdout.splitlines())
        metadata = subprocess.run(
            [str(seven_zip), "l", "-slt", str(installer)],
            capture_output=True, text=True, check=True, timeout=35,
        )
        filenames = {
            line.split(" = ", 1)[1].replace("\\", "/")
            for line in metadata.stdout.splitlines() if line.startswith("Path = ")
        }
        untracked = sorted(name for name in filenames if name.endswith(".py")
                           and name not in tracked)
        if (untracked or any(name not in filenames for name in OVERLAY_FILES)
                or "rag/runtime/incremental_installed_queue_init.py" in filenames):
            return {**blocked, "reason": "UNCOMMITTED_OR_MISSING_PYTHON",
                    "unexpected": untracked[:8]}
        with TemporaryDirectory(prefix="codebridge_p9b_nsis_audit_") as temp:
            unpack = subprocess.run(
                [str(seven_zip), "x", "-y", "-o"+str(temp),
                 str(installer), *OVERLAY_FILES],
                capture_output=True, text=True, check=True, timeout=70,
            )
            if unpack.returncode != 0:
                return blocked
            for relative in OVERLAY_FILES:
                path = Path(temp) / relative
                if not path.is_file() or path.is_symlink():
                    return blocked
                git_bytes = subprocess.run(
                    ["git", "-C", str(repo), "show",
                     f"{expected_commit}:{relative}"],
                    capture_output=True, check=True, timeout=10,
                ).stdout
                if path.read_bytes().replace(b"\r\n", b"\n") != git_bytes:
                    return {**blocked, "reason": "MODULE_CONTENT_MISMATCH"}
        return {"state": "P9B_NSIS_GIT_PAYLOAD_VERIFIED", "verified": True,
                "source_commit": expected_commit, "module_count": len(OVERLAY_FILES),
                "noncommitted_python": 0, "payload_entries": len(filenames),
                "sha256": hashlib.sha256(Path(installer).read_bytes()).hexdigest(),
                "installer_executed": False, "installed_modified": False}
    except (OSError, ValueError, subprocess.SubprocessError):
        return blocked
