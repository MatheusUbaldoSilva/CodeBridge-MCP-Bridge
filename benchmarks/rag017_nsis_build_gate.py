"""Read-only preflight for experimental NSIS compilation, never runs installer."""
import argparse,json,shutil,os
from pathlib import Path

def check(root:Path, compiler=None):
 root=Path(root)
 exe=root/"installer"/"dist"/"CodeBridge-Setup.exe"
 inputs=[root/"installer"/"CodeBridge.nsi",root/"installer"/"bootstrap.ps1",root/"author_mcp"/"mcp_server.py"]
 inputs.extend((root/"rag").rglob("*.py"))
 missing=[str(p) for p in inputs if not p.is_file()]
 build_time=exe.stat().st_mtime if exe.is_file() else None
 latest=max((p.stat().st_mtime for p in inputs if p.is_file()),default=None)
 compiler=compiler or shutil.which("makensis")
 if not compiler:
  candidates=[Path(os.environ.get("ProgramFiles(x86)",r"C:\\Program Files (x86)"))/"NSIS"/"makensis.exe",Path(os.environ.get("ProgramFiles",r"C:\\Program Files"))/"NSIS"/"makensis.exe"]
  compiler=next((str(p) for p in candidates if p.is_file()),None)
 result={"compiler_found":bool(compiler and Path(compiler).is_file()),"installer_exists":exe.is_file(),
 "installer_newer_than_inputs":bool(build_time is not None and latest is not None and build_time>=latest),
 "input_count":len(inputs),"missing_inputs":missing,
 "compilation_verified":False,"installation_verified":False,"rollback_verified":False}
 result["compile_preflight_passed"]=result["compiler_found"] and not missing
 return result

if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--root",required=True,type=Path)
 a=p.parse_args()
 data=check(a.root)
 print(json.dumps(data,indent=2))
 raise SystemExit(0 if data["compile_preflight_passed"] else 2)
