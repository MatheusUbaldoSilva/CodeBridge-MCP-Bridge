"""Read-only SHA-256 evidence for an offline CodeBridge runtime update."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def fingerprint(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        return {"exists": False, "sha256": None, "bytes": None}
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as handle:
        for piece in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(piece)
            count += len(piece)
    return {"exists": True, "sha256": digest.hexdigest(), "bytes": count}


def collect_runtime_fingerprints(install_root: Path, rag_state: Path) -> dict:
    """Compute only file hashes; no writes and no directory modifications."""
    root = Path(install_root)
    rag = Path(rag_state)
    paths = {
        "python_path": root / "runtime" / "python" / "python313._pth",
        "runtime_python": root / "runtime" / "python" / "python.exe",
        "runtime_requirements": root / "requirements.txt",
        "app_version": root / "version.json",
        "rag_manifest": rag / "rag-index-manifest.json",
        "rag_sqlite": rag / "rag_index.sqlite3",
    }
    return {
        "state": "READ_ONLY_RUNTIME_FINGERPRINTS",
        "files": {name: fingerprint(path) for name, path in paths.items()},
        "writes_performed": False,
        "public_index_updated": False,
    }



def compare_runtime_fingerprints(before: dict, after: dict) -> dict:
    """Fail closed if either public SQLite or manifest changes."""
    before_files = before.get("files", {})
    after_files = after.get("files", {})
    protected = ("rag_manifest", "rag_sqlite")
    matches = {}
    for name in protected:
        old, new = before_files.get(name, {}), after_files.get(name, {})
        matches[name] = bool(
            old.get("exists") and new.get("exists")
            and old.get("sha256") and old.get("sha256") == new.get("sha256")
            and old.get("bytes") == new.get("bytes"))
    changed = sorted(
        name for name in set(before_files) | set(after_files)
        if before_files.get(name) != after_files.get(name)
    )
    intact = all(matches.values())
    return {
        "state": "PUBLIC_INDEX_UNCHANGED" if intact else "PUBLIC_INDEX_INTEGRITY_BLOCKED",
        "public_index_intact": intact,
        "protected_matches": matches,
        "changed_entries": changed,
        "writes_performed": False,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--rag-state", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(collect_runtime_fingerprints(
        args.install_root, args.rag_state), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
