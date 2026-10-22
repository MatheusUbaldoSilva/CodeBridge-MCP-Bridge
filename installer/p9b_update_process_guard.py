"""Read-only CodeBridge updater process gate, independent of Qt/UI.

Conservative: an unreadable process list is UNKNOWN -> installation blocked.
Never stops a process or modifies local installation.
"""
from __future__ import annotations

from pathlib import Path
import ntpath


def inspect_update_processes(install_root: Path, *, process_iter=None) -> dict:
    def result(state: str, blockers: list[str], **details) -> dict:
        return {
            "state": state, "blockers": blockers,
            "installer_launch_authorized": False,
            "processes_stopped": False, "files_modified": False,
            "read_only": True, **details,
        }

    root=Path(install_root).resolve()
    if not root.is_dir():
        return result("UPDATE_PROCESS_UNVERIFIED",
                      ["INSTALL_ROOT_NOT_FOUND"])
    if process_iter is None:
        try:
            import psutil
            process_iter=psutil.process_iter(attrs=("pid", "name", "cmdline"))
        except Exception:
            return result("UPDATE_PROCESS_UNVERIFIED",
                          ["PROCESS_ENUMERATION_UNAVAILABLE"])
    root_string=ntpath.normcase(ntpath.normpath(str(root)))
    gui_path=ntpath.normcase(ntpath.join(root_string, "app_rewrite", "main.py"))
    mcp_path=ntpath.normcase(ntpath.join(root_string, "author_mcp", "mcp_server.py"))
    checked=0
    matched=[]
    try:
        for proc in process_iter:
            try:
                info=proc.info
                parts=info.get("cmdline") or []
                if isinstance(parts,str):
                    parts=[parts]
                # Compare complete argv tokens. Substring matching can
                # confuse a foreign script containing the installation path.
                args={ntpath.normcase(ntpath.normpath(str(arg).strip('"')))
                      for arg in parts}
                gui=gui_path in args
                mcp=mcp_path in args
                if gui or mcp:
                    matched.append({"pid": int(info.get("pid") or 0),
                                    "component": "GUI" if gui else "MCP"})
                checked+=1
            except Exception:
                return result("UPDATE_PROCESS_UNVERIFIED",
                              ["PROCESS_ACCESS_UNVERIFIED"], inspected=checked)
    except Exception:
        return result("UPDATE_PROCESS_UNVERIFIED",
                      ["PROCESS_ENUMERATION_FAILED"], inspected=checked)
    blockers=[]
    if any(p["component"]=="GUI" for p in matched):
        blockers.append("CODEBRIDGE_GUI_RUNNING")
    if any(p["component"]=="MCP" for p in matched):
        blockers.append("CODEBRIDGE_MCP_RUNNING")
    return result("UPDATE_PROCESS_BLOCKED" if blockers else "NO_RUNNING_CODEBRIDGE",
                  blockers, inspected=checked, matched=matched)



def main(argv=None) -> int:
    """Exit 0 only if the installed GUI and MCP are both known stopped."""
    import argparse
    import json
    parser=argparse.ArgumentParser()
    parser.add_argument("--install-root",type=Path,required=True)
    options=parser.parse_args(argv)
    report=inspect_update_processes(options.install_root)
    print(json.dumps(report,sort_keys=True))
    return 0 if report["state"] == "NO_RUNNING_CODEBRIDGE" else 2


if __name__=="__main__":
    raise SystemExit(main())
