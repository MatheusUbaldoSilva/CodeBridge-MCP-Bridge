"""Build a fail-closed manifest for a Git-archived, isolated CodeBridge candidate.

No Git updates, overwrites, installation changes, or data migrations.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess


def create_manifest(root: Path, destination: Path, repository: Path, ref: str = "HEAD"):
    if root.is_symlink() or root.is_junction():
        raise RuntimeError("SNAPSHOT_REPARSE_BLOCKED")
    root = root.resolve(strict=True)
    if destination.exists():
        raise RuntimeError("MANIFEST_ALREADY_EXISTS")
    commit = subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", "--verify", ref + "^{commit}"],
        text=True, encoding="utf-8",
    ).strip()
    names = subprocess.check_output(
        ["git", "-C", str(repository), "ls-tree", "-r", "--name-only", commit],
        text=True, encoding="utf-8",
    ).splitlines()
    if len(names) < 100 or not (root / "app_rewrite" / "main.py").is_file():
        raise RuntimeError("SNAPSHOT_INCOMPLETE")
    entries = {}
    for name in names:
        path = root / name
        if path.is_symlink() or path.is_junction() or not path.is_file():
            raise RuntimeError("FILE_MISSING_OR_REPARSE: " + name)
        if not path.resolve().is_relative_to(root):
            raise RuntimeError("PATH_OUTSIDE_ROOT: " + name)
        h = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                h.update(block)
        entries[name] = h.hexdigest()
    extra = []
    for file in root.rglob("*"):
        if file.is_file() and file.relative_to(root).as_posix() not in entries:
            extra.append(str(file.relative_to(root)))
    if extra:
        raise RuntimeError("SNAPSHOT_EXTRA_FILES: " + str(extra[:3]))
    payload = {
        "state": "CANDIDATE",
        "promotion_authorized": False,
        "source_commit": commit,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checksums": entries,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as out:
        json.dump(payload, out, ensure_ascii=False, indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    return commit, len(entries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repository", default=Path.home() / "CodeBridge-MCP-Bridge", type=Path)
    parser.add_argument("--ref", default="HEAD")
    args = parser.parse_args()
    sha, count = create_manifest(args.root, args.manifest, args.repository, args.ref)
    print("SNAPSHOT_MANIFEST_OK commit=%s files=%d" % (sha, count))
