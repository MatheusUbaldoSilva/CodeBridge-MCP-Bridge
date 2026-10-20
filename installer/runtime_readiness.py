"""Read-only evidence of installed CodeBridge embedded Python readiness."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess

REQUIRED_ROOT_LINE = r"..\.."
MODULES = ("rag", "qdrant_client", "PySide6", "psutil", "paramiko")


def inspect_embedded_runtime(install_root: Path) -> dict:
    root = Path(install_root)
    python = root / "runtime" / "python" / "python.exe"
    pth = root / "runtime" / "python" / "python313._pth"
    result = {
        "ready": False,
        "runtime_present": python.is_file(),
        "pth_present": pth.is_file(),
        "root_path_exposed": False,
        "modules": {key: False for key in MODULES},
        "errors": [],
        "modifies_runtime": False,
    }
    if not python.is_file() or not pth.is_file():
        result["errors"].append("RUNTIME_OR_PTH_MISSING")
        return result
    lines = [x.strip() for x in pth.read_text(encoding="ascii").splitlines()
             if x.strip() and not x.lstrip().startswith("#")]
    result["root_path_exposed"] = REQUIRED_ROOT_LINE in lines
    if not result["root_path_exposed"]:
        result["errors"].append("INSTALL_ROOT_NOT_ON_PYTHON_PATH")
    code = ("import importlib.util,json;"
            "names=" + repr(list(MODULES)) + ";"
            "print(json.dumps({n:bool(importlib.util.find_spec(n)) for n in names}))")
    try:
        check = subprocess.run([str(python), "-c", code],
                               capture_output=True, text=True, timeout=15)
        if check.returncode:
            result["errors"].append("PYTHON_PROBE_FAILED")
        else:
            parsed = json.loads(check.stdout.strip())
            result["modules"] = {key: bool(parsed.get(key)) for key in MODULES}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        result["errors"].append("PYTHON_PROBE_UNAVAILABLE")
    for module, available in result["modules"].items():
        if not available:
            result["errors"].append("MISSING_MODULE_" + module.upper())
    result["ready"] = not result["errors"]
    return result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", type=Path, required=True)
    args = parser.parse_args()
    result = inspect_embedded_runtime(args.install_root)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
