"""Read-only maintenance preflight for CodeBridge embedded Python.

Never writes installed files, stops processes or promotes a RAG index.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from installer.runtime_readiness import inspect_embedded_runtime
from installer.runtime_staging_verify import verify_staged_embedded_runtime
from installer.runtime_fingerprints import collect_runtime_fingerprints


def assess_runtime_maintenance(install_root: Path, repo_root: Path,
                               dependencies_root: Path) -> dict:
    install = Path(install_root).resolve()
    repo = Path(repo_root).resolve()
    deps = Path(dependencies_root).resolve()
    active = inspect_embedded_runtime(install)
    staged = verify_staged_embedded_runtime(install, repo, deps)
    baseline = collect_runtime_fingerprints(
        install, Path.home() / "AppData" / "Local" / "CodeBridge" / "rag")
    public_complete = all(
        baseline["files"][name]["exists"]
        for name in ("rag_manifest", "rag_sqlite")
    )
    return {
        "state": ("MISSING_PUBLIC_INDEX_BASELINE" if not public_complete else
                  "READY_ALREADY_INSTALLED" if active["ready"] else
                  "OFFLINE_MAINTENANCE_CANDIDATE" if staged["validated"] else
                  "MAINTENANCE_BLOCKED"),
        "current_runtime": active,
        "isolated_stage": staged,
        "public_index_fingerprints": {
            k: baseline["files"][k] for k in ("rag_manifest", "rag_sqlite")
        },
        "requires_codebridge_closed": not active["ready"],
        "operator_approval_required": not active["ready"],
        "applied": False,
        "stop_requested": False,
        "installed_files_changed": False,
        "public_index_updated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--dependencies-root", type=Path, required=True)
    args = parser.parse_args()
    result = assess_runtime_maintenance(
        args.install_root, args.repo_root, args.dependencies_root)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] in ("READY_ALREADY_INSTALLED", "OFFLINE_MAINTENANCE_CANDIDATE") else 2


if __name__ == "__main__":
    raise SystemExit(main())
