"""Read-only installer payload inventory and reversible installed-file snapshot.

No installer execution, service stop, restored files, secrets or RAG data.
Only the files explicitly present in the audited NSIS payload are in scope.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile


_ALLOWED_ROOTS = {
    "app_rewrite", "author_mcp", "rag", "assets",
    "installer", "browser_extension", "tools",
}
_ALLOWED_FILES = {"requirements.txt", "README.md", "version.json",
                  "docs/DESKTOP_DEPLOYMENT_CURRENT.md"}
_DENIED_PARTS = {".env", ".ssh", "secrets", "private", "credentials"}
_DENIED_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".sqlite", ".db"}


def payload_file_list(executable: Path, seven_zip: Path) -> tuple[str, ...]:
    if not executable.is_file() or executable.is_symlink() or not seven_zip.is_file():
        raise ValueError("PAYLOAD_NOT_READABLE")
    result = subprocess.run(
        [str(seven_zip), "l", "-slt", str(executable)],
        capture_output=True, text=True, check=True, timeout=35,
    )
    names = []
    for line in result.stdout.splitlines():
        if not line.startswith("Path = "):
            continue
        raw = line[7:].replace("\\", "/")
        if raw == str(executable).replace("\\", "/") or raw.startswith("$PLUGINSDIR/") or raw == "$PLUGINSDIR":
            continue
        p = PurePosixPath(raw)
        if (not p.parts or p.is_absolute() or len(p.parts) > 10
                or any(part in ("", ".", "..") or ":" in part for part in p.parts)
                or len(raw) > 250):
            raise ValueError("UNSAFE_INSTALLER_TARGET")
        if (p.parts[0] not in _ALLOWED_ROOTS and raw not in _ALLOWED_FILES):
            raise ValueError("UNAPPROVED_INSTALLER_TARGET")
        if (set(x.lower() for x in p.parts) & _DENIED_PARTS
                or p.suffix.lower() in _DENIED_SUFFIXES):
            raise ValueError("UNEXPECTED_SENSITIVE_INSTALLER_TARGET")
        names.append(raw)
    if (not 100 <= len(names) <= 2000
            or len(set(x.lower() for x in names)) != len(names)
            or "author_mcp/mcp_server.py" not in names
            or "rag/runtime/incremental_authorized_queue_bootstrap.py" not in names
            or "rag/runtime/incremental_installed_queue_init.py" in names):
        raise ValueError("INSTALLER_PAYLOAD_NOT_APPROVED")
    return tuple(sorted(names))


def snapshot_installer_overwrites(
    installer: Path, seven_zip: Path, installed: Path, archive_path: Path,
    *, execute: bool = False,
) -> dict:
    result = {"state": "INSTALLER_ROLLBACK_BLOCKED", "created": False,
              "installer_executed": False, "installed_modified": False}
    installed = Path(installed).resolve()
    archive_path = Path(archive_path).absolute()
    if (archive_path.exists() or archive_path.is_symlink()
            or not archive_path.parent.is_dir()
            or archive_path.is_relative_to(installed)):
        return result
    try:
        targets = payload_file_list(Path(installer), Path(seven_zip))
        existing = {}
        total = 0
        for name in targets:
            path = installed.joinpath(*PurePosixPath(name).parts)
            if (path.is_symlink()
                    or any(parent.is_symlink() for parent in path.parents
                           if parent == installed or installed in parent.parents)):
                return {**result, "reason": "INSTALLED_PATH_IS_SYMLINK"}
            if path.exists():
                if not path.is_file():
                    return {**result, "reason": "UNEXPECTED_INSTALLED_TARGET_TYPE"}
                size = path.stat().st_size
                if size > 80_000_000:
                    return {**result, "reason": "INDIVIDUAL_INSTALLED_FILE_TOO_LARGE"}
                total += size
                existing[name] = path
        if total > 350_000_000:
            return {**result, "reason": "SNAPSHOT_TOO_LARGE"}
        if execute is not True:
            return {**result, "state": "INSTALLER_ROLLBACK_PLAN_ONLY",
                    "targets": len(targets), "existing_files": len(existing),
                    "existing_bytes": total, "missing_files": len(targets)-len(existing)}
        payload = {
            "schema": 1, "state": "INSTALLER_PREUPDATE_SNAPSHOT",
            "installed_root": str(installed),
            "installer_sha256": hashlib.sha256(Path(installer).read_bytes()).hexdigest(),
            "targets": list(targets), "existing": {},
            "restored": False, "installed_modified": False,
        }
        with archive_path.open("xb") as stream:
            with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
                for name, file in existing.items():
                    data = file.read_bytes()
                    if len(data) + total > 800_000_000:
                        raise ValueError("SNAPSHOT_CHANGED")
                    hash_before = hashlib.sha256(data).hexdigest()
                    if hashlib.sha256(file.read_bytes()).hexdigest() != hash_before:
                        raise ValueError("INSTALLED_FILE_CHANGED_DURING_SNAPSHOT")
                    archive.writestr("old/"+name, data)
                    payload["existing"][name] = {
                        "sha256": hash_before, "bytes": len(data),
                    }
                archive.writestr("manifest.json",json.dumps(payload,sort_keys=True))
        return {**result, "state": "INSTALLER_ROLLBACK_SNAPSHOT_CREATED",
                "created": True, "files": len(existing),
                "targets": len(targets),
                "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest()}
    except (OSError, ValueError, subprocess.SubprocessError):
        # Never delete a potentially partial archive: preserve for investigation.
        return {**result, "state": "INSTALLER_ROLLBACK_REVIEW_REQUIRED",
                "created": archive_path.exists()}


def _valid_installer_target(name: str) -> bool:
    if not isinstance(name, str) or len(name) > 250:
        return False
    p=PurePosixPath(name)
    if (not p.parts or p.is_absolute() or len(p.parts)>10
            or any(c in ("", ".", "..") or ":" in c or "\\\\" in c
                   for c in p.parts)):
        return False
    if p.parts[0] not in _ALLOWED_ROOTS and name not in _ALLOWED_FILES:
        return False
    return not (set(x.lower() for x in p.parts) & _DENIED_PARTS
                or p.suffix.lower() in _DENIED_SUFFIXES)


def verify_installer_rollback_snapshot(archive_path: Path, installed: Path) -> dict:
    result = {"state": "INSTALLER_ROLLBACK_UNVERIFIED", "verified": False,
              "restored": False, "installed_modified": False}
    path = Path(archive_path)
    if not path.is_file() or path.is_symlink():
        return result
    try:
        with closing(ZipFile(path)) as archive:
            listing=archive.namelist()
            if len(listing)!=len(set(listing)) or "manifest.json" not in listing:
                return result
            payload=json.loads(archive.read("manifest.json"))
            if (payload["schema"] != 1 or
                    Path(payload["installed_root"]).resolve() != Path(installed).resolve()
                    or payload["state"] != "INSTALLER_PREUPDATE_SNAPSHOT"
                    or not isinstance(payload["targets"],list)
                    or not isinstance(payload["existing"],dict)):
                return result
            target_set=set(payload["targets"])
            if (len(target_set)!=len(payload["targets"])
                    or not 100 <= len(target_set) <= 2000
                    or any(not _valid_installer_target(x) for x in target_set)
                    or not set(payload["existing"]).issubset(target_set)):
                return result
            expected={"manifest.json"}
            for rel, meta in payload["existing"].items():
                if (PurePosixPath(rel).is_absolute() or
                        ".." in PurePosixPath(rel).parts or
                        rel not in target_set):
                    return result
                name="old/"+rel
                expected.add(name)
                info=archive.getinfo(name)
                if info.file_size != meta["bytes"] or info.file_size>80_000_000:
                    return result
                if hashlib.sha256(archive.read(name)).hexdigest()!=meta["sha256"]:
                    return result
            if expected != set(listing):
                return result
        return {**result, "state": "INSTALLER_ROLLBACK_SNAPSHOT_VERIFIED",
                "verified": True, "existing_files": len(payload["existing"]),
                "installer_sha256": payload["installer_sha256"],
                "targets": len(target_set)}
    except (OSError, ValueError, KeyError, TypeError, BadZipFile):
        return result



def inspect_installer_snapshot_baseline(archive_path: Path, installed: Path) -> dict:
    """Checks byte-exact pre-install state; read-only even on mismatch."""
    baseline={"state":"INSTALLED_BASELINE_MISMATCH","matches":False,
              "installed_modified":False,"restored":False}
    validation=verify_installer_rollback_snapshot(archive_path,installed)
    if not validation["verified"]:
        return baseline
    try:
        with closing(ZipFile(archive_path)) as z:
            data=json.loads(z.read("manifest.json"))
            old=data["existing"]
            root=Path(installed).resolve()
            for rel in data["targets"]:
                path=root.joinpath(*PurePosixPath(rel).parts)
                if path.is_symlink() or any(
                    parent.is_symlink() for parent in path.parents
                    if parent == root or root in parent.parents
                ):
                    return baseline
                if rel not in old:
                    if path.exists():
                        return baseline
                else:
                    if not path.is_file():
                        return baseline
                    if (path.stat().st_size != old[rel]["bytes"]
                            or hashlib.sha256(path.read_bytes()).hexdigest()
                            != old[rel]["sha256"]):
                        return baseline
        return {**baseline,"state":"INSTALLED_BASELINE_MATCH",
                "matches":True,"files_checked":len(old)}
    except (OSError, ValueError, KeyError, TypeError, BadZipFile):
        return baseline


def rehearse_installer_restore_scratch(archive_path: Path,
                                      installed: Path, scratch: Path) -> dict:
    """Materializes old files ONLY in an empty disposable directory."""
    result={"state":"RESTORE_REHEARSAL_BLOCKED","rehearsed":False,
            "installed_modified":False,"production_restore_performed":False}
    checked=verify_installer_rollback_snapshot(archive_path,installed)
    base=Path(installed).resolve()
    scratch=Path(scratch).absolute()
    if (not checked["verified"] or scratch.exists() or scratch.is_symlink()
            or not scratch.parent.is_dir() or scratch.is_relative_to(base)):
        return result
    try:
        scratch.mkdir()
        with closing(ZipFile(archive_path)) as archive:
            manifest=json.loads(archive.read("manifest.json"))
            for rel, meta in manifest["existing"].items():
                relative=PurePosixPath(rel)
                if not _valid_installer_target(rel):
                    raise ValueError("UNSAFE_RESTORE_NAME")
                dest=scratch.joinpath(*relative.parts)
                if not dest.resolve(strict=False).is_relative_to(scratch):
                    raise ValueError("RESTORE_OUTSIDE_SCRATCH")
                dest.parent.mkdir(parents=True,exist_ok=True)
                bytes_original=archive.read("old/"+rel)
                if hashlib.sha256(bytes_original).hexdigest()!=meta["sha256"]:
                    raise ValueError("ARCHIVE_CHANGED")
                dest.write_bytes(bytes_original)
        return {**result,"state":"ISOLATED_INSTALLER_RESTORE_REHEARSED",
                "rehearsed":True,"files":len(manifest["existing"]),
                "scratch_path":str(scratch)}
    except (OSError, ValueError, KeyError, BadZipFile):
        # Keep partial scratch for investigation, never erase user files.
        return {**result,"state":"ISOLATED_RESTORE_REVIEW_REQUIRED",
                "scratch_path":str(scratch) if scratch.exists() else None}
