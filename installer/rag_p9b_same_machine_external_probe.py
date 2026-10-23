"""Independent Windows interpreter preflight before replacing CodeBridge.

Read-only. Does not stop processes, start NSIS or write registry/files.
The interpreter AND psutil must both live outside the installed tree.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys

def inspect_external_runtime(*,installed,interpreter,psutil_origin,staged_lib):
    denied={"state":"EXTERNAL_RUNTIME_REFUSED","verified":False,
            "installer_executed":False,"production_modified":False}
    try:
        installed=Path(installed).resolve()
        python=Path(interpreter).resolve()
        module=Path(psutil_origin).resolve()
        lib=Path(staged_lib).resolve()
        if (not python.is_file() or python.is_relative_to(installed)
                or not module.is_file() or not module.is_relative_to(lib)
                or lib.is_relative_to(installed)):
            return {**denied,"reason":"DEPENDENCY_STILL_INSIDE_INSTALLED_APP"}
        return {**denied,"state":"EXTERNAL_RUNTIME_PATHS_VERIFIED",
                "verified":True}
    except (OSError,ValueError,TypeError):
        return {**denied,"reason":"EXTERNAL_PATH_VERIFICATION_ERROR"}


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--installed",required=True)
    parser.add_argument("--stage",required=True)
    parser.add_argument("--identity",required=True)
    parser.add_argument("--identity-sha",required=True)
    parser.add_argument("--worktree",required=True)
    options=parser.parse_args(argv)
    stage=Path(options.stage).resolve()
    dependency=stage/"external_supervisor_lib"
    if dependency.is_symlink() or not dependency.is_dir():
        print(json.dumps({"state":"EXTERNAL_DEPENDENCY_MISSING","verified":False}))
        return 2
    sys.path.insert(0,str(dependency))
    try:
        import psutil
        proof=inspect_external_runtime(installed=options.installed,
            interpreter=sys.executable,psutil_origin=psutil.__file__,staged_lib=dependency)
        if not proof["verified"]:
            print(json.dumps(proof,sort_keys=True))
            return 2
        if not Path(options.identity).resolve().is_relative_to(stage):
            print(json.dumps({"state":"EXTERNAL_IDENTITY_OUTSIDE_STAGING","verified":False}))
            return 2
        from installer.rag_p9b_current_machine_cutover_gate import assess
        report=assess(identity=options.identity,identity_sha=options.identity_sha,
            installed=options.installed,worktree=options.worktree,
            appdata=Path(os.environ["APPDATA"]),desktop=Path.home()/"Desktop")
        report["external_runtime_verified"]=True
        report["mode"]="EXTERNAL_READ_ONLY_PREFLIGHT"
        print(json.dumps(report,sort_keys=True))
        return 2
    except Exception as error:
        print(json.dumps({"state":"EXTERNAL_PREFLIGHT_EXCEPTION",
                          "verified":False,"error_type":type(error).__name__}))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
