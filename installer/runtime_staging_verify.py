"""Read-only isolated validation before repairing an installed CodeBridge runtime."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess

_CHECK = """import importlib,json,sys
from importlib import metadata
sys.path[:0]=[sys.argv[1],sys.argv[2]]
import rag.runtime.incremental_offline_worker as worker
import qdrant_client
from rag.runtime.incremental_bundle_validate import validate_incremental_bundle
print(json.dumps({'qdrant_version':metadata.version('qdrant-client'),
                  'worker_ready':callable(worker.process_offline_job_once),
                  'validator_ready':callable(validate_incremental_bundle),
                  'tested_with_injected_paths':True}))
"""


def verify_staged_embedded_runtime(
    install_root: Path, repo_root: Path, dependencies_root: Path,
) -> dict:
    """No import execution until inputs are validated. Does not write files."""
    install = Path(install_root).resolve()
    repo = Path(repo_root).resolve()
    dependencies = Path(dependencies_root).resolve()
    executable = install / "runtime" / "python" / "python.exe"
    result = {"state": "STAGING_UNAVAILABLE", "validated": False,
              "live_runtime_updated": False, "public_index_updated": False}
    if not executable.is_file() or not (repo / "rag" / "__init__.py").is_file():
        return result
    if not dependencies.is_dir() or not (dependencies / "qdrant_client").is_dir():
        return result
    if (dependencies == install or dependencies == repo or
            dependencies.is_relative_to(install) or
            dependencies.is_relative_to(repo)):
        return {"state": "STAGING_NOT_ISOLATED", "validated": False,
                "live_runtime_updated": False, "public_index_updated": False}
    try:
        check = subprocess.run(
            [str(executable), "-c", _CHECK, str(dependencies), str(repo)],
            capture_output=True, text=True, timeout=45,
        )
        if check.returncode != 0:
            return {**result, "state": "STAGING_IMPORT_FAILED"}
        values = json.loads(check.stdout.strip())
        if not (values.get("qdrant_version") == "1.19.1" and
                values.get("worker_ready") and values.get("validator_ready")):
            return {**result, "state": "STAGING_CONTRACT_MISMATCH"}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {**result, "state": "STAGING_PROBE_FAILED"}
    return {"state": "STAGING_IMPORTS_VALIDATED", "validated": True,
            "qdrant_version": "1.19.1", "live_runtime_updated": False,
            "public_index_updated": False}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--dependencies-root", required=True, type=Path)
    args = parser.parse_args()
    result = verify_staged_embedded_runtime(
        args.install_root, args.repo_root, args.dependencies_root)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["validated"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
