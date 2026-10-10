"""Transactional rollback rehearsal entirely inside a disposable TEMP directory."""
import argparse, hashlib, json, shutil
from pathlib import Path

def digest(tree):
    return {str(p.relative_to(tree)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in tree.rglob("*") if p.is_file()}

def run(root: Path):
    root = root.resolve()
    if root.parent.name.lower() != "temp" or not root.name.startswith("CodeBridge-RAG017-RollbackLab-") or root.exists():
        raise ValueError("only a fresh direct TEMP laboratory path is allowed")
    install = root / "simulated_install"
    backup = root / "pre_update_backup"
    install.mkdir(parents=True)
    baseline = {
      "app_rewrite/main.py": b"ORIGINAL_APP\n",
      "author_mcp/mcp_server.py": b"ORIGINAL_MCP\n",
      "runtime/python/python313._pth": b"ORIGINAL_PTH\n",
      "settings/company_config.json": b'{"company":"keep-me"}\n',
      "registry/HKCU_CodeBridge.json": b'{"InstallDir":"original","Version":"original"}\n',
      "shortcuts/CodeBridge.lnk": b"ORIGINAL_SHORTCUT\n",
    }
    for name, data in baseline.items():
        dest = install / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    initial = digest(install)
    shutil.copytree(install, backup)
    if digest(backup) != initial: raise RuntimeError("backup mismatch")
    update = {"app_rewrite/main.py": b"EXPERIMENTAL_APP",
              "author_mcp/mcp_server.py": b"EXPERIMENTAL_MCP",
              "runtime/python/python313._pth": b"EXPERIMENTAL_PTH",
              "registry/HKCU_CodeBridge.json": b"EXPERIMENTAL_REGISTRY",
              "shortcuts/CodeBridge.lnk": b"EXPERIMENTAL_SHORTCUT",
              "rag/new_module.py": b"NEW_RAG"}
    for name, data in update.items():
        dest = install / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    shutil.rmtree(install)
    shutil.copytree(backup, install)
    restored = digest(install)
    success = initial == restored and not (install / "rag").exists()
    outcome = {"lab_only": True, "backed_up_files": len(initial),
               "injected_changes": len(update), "restored_identical": success,
               "new_files_removed": not (install / "rag").exists(),
               "registry_real_modified": False, "shortcuts_real_modified": False,
               "actual_nsis_rollback_verified": False}
    print(json.dumps(outcome, sort_keys=True))
    if not success: raise RuntimeError("rollback rehearsal failed")
    return outcome

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    run(args.root)
