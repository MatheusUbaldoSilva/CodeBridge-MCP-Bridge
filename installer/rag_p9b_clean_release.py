"""Build P9-B installer previews from exact committed Git objects.

Never invokes installer, touches installed CodeBridge, or packages untracked
worktree files. Only explicitly allowlisted tunnel binaries supplement Git.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
from tempfile import TemporaryDirectory


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_committed_release(repo: Path, destination: Path) -> dict:
    repo = Path(repo).resolve()
    dest = Path(destination).absolute()
    if dest.exists() or dest.is_symlink() or not dest.parent.is_dir():
        return {"state": "EXPORT_REFUSED", "exported": False}
    try:
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, check=True, timeout=10, text=True,
        ).stdout.strip()
        if len(head) != 40 or any(c not in "0123456789abcdef" for c in head):
            return {"state": "SOURCE_COMMIT_UNVERIFIED", "exported": False}
        result = subprocess.run(
            ["git", "-C", str(repo), "archive", "--format=tar", head],
            capture_output=True, check=True, timeout=90,
        )
        files = []
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
            names = set()
            for entry in archive:
                path = PurePosixPath(entry.name)
                if (path.is_absolute() or any(p in ("", ".", "..") for p in path.parts)
                        or entry.name in names
                        or not (entry.isfile() or entry.isdir())):
                    return {"state": "UNSAFE_GIT_ARCHIVE", "exported": False}
                names.add(entry.name)
                files.append(entry)
            # Only mutate a brand-new staging tree after all paths validated.
            dest.mkdir()
            with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
                for entry in archive:
                    target = dest.joinpath(*PurePosixPath(entry.name).parts)
                    if entry.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with target.open("xb") as f:
                            source = archive.extractfile(entry)
                            if source is None:
                                raise OSError("Archive file unavailable")
                            shutil.copyfileobj(source, f)
        return {"state": "COMMITTED_TREE_EXPORTED",
                "exported": True, "commit": head,
                "file_count": sum(item.isfile() for item in files)}
    except (OSError, ValueError, tarfile.TarError,
            subprocess.SubprocessError):
        if dest.exists():
            shutil.rmtree(dest)
        return {"state": "EXPORT_FAILED", "exported": False}


def build_p9b_preview(repo: Path, payload: Path, output: Path,
                      makensis: Path, seven_zip: Path) -> dict:
    repo = Path(repo).resolve()
    payload = Path(payload).resolve()
    output = Path(output).absolute()
    fail = {"state": "CLEAN_INSTALLER_BUILD_FAILED", "built": False,
            "installed_modified": False, "installer_executed": False}
    if (output.exists() or output.is_symlink() or not output.parent.is_dir()
            or not makensis.is_file() or not seven_zip.is_file()):
        return fail
    with TemporaryDirectory(prefix="codebridge_clean_p9b_") as tmp:
        tree = Path(tmp) / "snapshot"
        exported = export_committed_release(repo, tree)
        if not exported["exported"]:
            return {**fail, "reason": exported["state"]}
        for name in ("tunnel-client.exe", "cloudflared.exe"):
            src = payload / name
            dest = tree / "installer" / "payload" / "tools" / name
            if not src.is_file() or src.is_symlink() or src.stat().st_size < 100000:
                return {**fail, "reason": "APPROVED_BINARY_PAYLOAD_MISSING"}
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        # Old tracked release artifacts in the Git snapshot are not inputs.
        dist = tree / "installer" / "dist"
        if dist.exists():
            shutil.rmtree(dist)
        dist.mkdir()
        try:
            compiled = subprocess.run(
                [str(makensis), "/V2", "/INPUTCHARSET", "UTF8",
                 str(tree / "installer" / "CodeBridge.nsi")],
                cwd=str(tree / "installer"),
                capture_output=True, text=True, timeout=180,
            )
            binary = dist / "CodeBridge-Setup.exe"
            if compiled.returncode != 0 or not binary.is_file():
                return {**fail, "reason": "NSIS_COMPILE_FAILED",
                        "compiler_tail": compiled.stdout[-600:] + compiled.stderr[-600:]}
            listing = subprocess.run(
                [str(seven_zip), "l", "-slt", str(binary)],
                capture_output=True, text=True, timeout=30, check=True,
            )
            paths = {
                line.split(" = ", 1)[1].replace("\\", "/")
                for line in listing.stdout.splitlines() if line.startswith("Path = ")
            }
            expected = {
                "author_mcp/mcp_server.py",
                "rag/runtime/incremental_authorized_queue_bootstrap.py",
                "rag/runtime/incremental_installed_queue_bootstrap_preflight.py",
                "rag/runtime/incremental_supervisor_lock.py",
                "rag/runtime/incremental_supervisor_fence.py",
                "rag/runtime/incremental_scheduler_public_pointer.py",
                "rag/runtime/incremental_job_queue.py",
            }
            if not expected.issubset(paths):
                return {**fail, "reason": "BOOTSTRAP_MODULES_MISSING"}
            tracked = set(subprocess.run(
                ["git", "-C", str(repo), "ls-tree", "-r", "--name-only",
                 exported["commit"]],
                capture_output=True, text=True, timeout=15, check=True,
            ).stdout.splitlines())
            rogue = sorted(name for name in paths if name.endswith(".py")
                           and name not in tracked)
            if rogue:
                return {**fail, "reason": "UNCOMMITTED_PYTHON_PAYLOAD",
                        "rejected_paths": rogue[:10]}
            shutil.copy2(binary, output)
            return {"state": "CLEAN_OFFLINE_INSTALLER_READY",
                    "built": True, "installed_modified": False,
                    "installer_executed": False,
                    "git_commit": exported["commit"],
                    "payload_entries": len(paths),
                    "sha256": _sha(output), "bytes": output.stat().st_size,
                    "path": str(output)}
        except (OSError, ValueError, subprocess.SubprocessError):
            if output.exists():
                output.unlink()
            return fail
