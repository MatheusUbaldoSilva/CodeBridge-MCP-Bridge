"""Read-only SHA-256 evidence for an offline CodeBridge runtime update."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def fingerprint(path: Path) -> dict:
    path = Path(path)
    if (path.is_symlink() or
            (hasattr(path, "is_junction") and path.is_junction())
            or not path.is_file()):
        return {"exists": False, "sha256": None, "bytes": None}
    digest = hashlib.sha256()
    count = 0
    try:
        with path.open("rb") as handle:
            for piece in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(piece)
                count += len(piece)
    except OSError:
        return {"exists": False, "sha256": None, "bytes": None}
    return {"exists": True, "sha256": digest.hexdigest(), "bytes": count}



def fingerprint_tree(root: Path) -> dict:
    """SHA-256 of canonical sorted relative paths, sizes and file hashes."""
    root = Path(root)
    if (not root.is_dir() or root.is_symlink()
            or (hasattr(root, "is_junction") and root.is_junction())):
        return {"exists": False, "sha256": None, "bytes": None, "file_count": None}
    digest = hashlib.sha256()
    total = 0
    count = 0
    try:
        paths = sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix())
        for path in paths:
            if (path.is_symlink()
                    or (hasattr(path, "is_junction") and path.is_junction())):
                return {"exists": False, "sha256": None, "bytes": None,
                        "file_count": None}
            if path.is_file():
                relative = path.relative_to(root).as_posix()
                evidence = fingerprint(path)
                if not evidence["exists"] or evidence["sha256"] is None:
                    raise OSError("Vector file vanished during fingerprint")
                payload = json.dumps([relative, evidence["bytes"], evidence["sha256"]],
                                     ensure_ascii=False, separators=(",", ":"))
                digest.update(payload.encode("utf-8") + b"\n")
                total += evidence["bytes"]
                count += 1
    except OSError:
        return {"exists": False, "sha256": None, "bytes": None,
                "file_count": None}
    if count == 0:
        return {"exists": False, "sha256": None, "bytes": None, "file_count": 0}
    return {"exists": True, "sha256": digest.hexdigest(), "bytes": total,
            "file_count": count}


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
    evidence = {name: fingerprint(path) for name, path in paths.items()}
    evidence["rag_qdrant"] = fingerprint_tree(rag / "qdrant")
    return {
        "state": "READ_ONLY_RUNTIME_FINGERPRINTS",
        "files": evidence,
        "writes_performed": False,
        "public_index_updated": False,
    }



def compare_runtime_fingerprints(before: dict, after: dict) -> dict:
    """Fail closed on public manifest, SQLite or Qdrant tree drift."""
    before_files = before.get("files") if isinstance(before, dict) else None
    after_files = after.get("files") if isinstance(after, dict) else None
    before_files = before_files if isinstance(before_files, dict) else {}
    after_files = after_files if isinstance(after_files, dict) else {}
    protected = ("rag_manifest", "rag_sqlite", "rag_qdrant")
    matches = {}
    for name in protected:
        old, new = before_files.get(name), after_files.get(name)
        old = old if isinstance(old, dict) else {}
        new = new if isinstance(new, dict) else {}
        matches[name] = bool(
            old.get("exists") and new.get("exists")
            and old.get("sha256") and old.get("sha256") == new.get("sha256")
            and old.get("bytes") == new.get("bytes")
            and old.get("file_count") == new.get("file_count"))
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



def compare_saved_public_baseline(baseline_path: Path, install_root: Path,
                                  rag_state: Path) -> dict:
    """Read a previously captured public SHA baseline and compare it to live files."""
    try:
        saved = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
        if (not isinstance(saved, dict) or saved.get("schema_version") != 1
                or saved.get("purpose") != "rag-public-index-read-only-maintenance-baseline"):
            raise ValueError("Invalid public baseline schema")
        required = ("rag_manifest", "rag_sqlite", "rag_qdrant")
        entries = saved.get("files")
        if not isinstance(entries, dict) or not all(
                isinstance(entries.get(item), dict) for item in required):
            raise ValueError("Incomplete public baseline")
        for item in required:
            value = entries[item]
            digest = value.get("sha256")
            size = value.get("bytes")
            if (value.get("exists") is not True
                    or not isinstance(digest, str) or len(digest) != 64
                    or any(ch not in "0123456789abcdef" for ch in digest)
                    or type(size) is not int or size < 0):
                raise ValueError("Invalid saved public fingerprint")
            if item == "rag_qdrant":
                count = value.get("file_count")
                if type(count) is not int or count < 1:
                    raise ValueError("Invalid Qdrant file count")
        before = {"files": {item: entries[item] for item in required}}
        live = collect_runtime_fingerprints(install_root, rag_state)
        after = {"files": {item: live.get("files", {}).get(item)
                           for item in required}}
        result = compare_runtime_fingerprints(before, after)
    except (OSError, ValueError, TypeError):
        return {"state": "PUBLIC_BASELINE_INVALID", "public_index_intact": False,
                "writes_performed": False}
    return result



def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--rag-state", type=Path, required=True)
    parser.add_argument("--compare-baseline", type=Path)
    args = parser.parse_args()
    if args.compare_baseline is not None:
        result = compare_saved_public_baseline(
            args.compare_baseline, args.install_root, args.rag_state)
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("public_index_intact") else 2
    print(json.dumps(collect_runtime_fingerprints(
        args.install_root, args.rag_state), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
