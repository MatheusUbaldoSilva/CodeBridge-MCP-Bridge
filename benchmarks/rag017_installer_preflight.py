"""Fail-closed read-only NSIS preflight for RAG-capable MCP upgrades."""
from pathlib import Path
import argparse,json,re

def check(nsis:Path,source_root:Path,installed_root:Path):
 text=nsis.read_text(encoding="utf-8-sig")
 required=("rag","author_mcp")
 has_rag=bool(re.search(r'SetOutPath\s+"\$INSTDIR\\rag"',text,re.I))
 has_rag_files=bool(re.search(r'File\s+/r\s+"\.\.\\rag\\',text,re.I))
 src=(source_root/"author_mcp"/"mcp_server.py").read_text(encoding="utf-8")
 local=installed_root/"author_mcp"/"mcp_server.py"
 installed=local.read_text(encoding="utf-8") if local.is_file() else ""
 report={"nsis_rag_destination":has_rag,"nsis_rag_recursive_copy":has_rag_files,
 "source_has_rag_tool":'name="codebridge_rag_status"' in src,
 "installed_has_rag_tool":'name="codebridge_rag_status"' in installed,
 "installed_rag_package":(installed_root/"rag").is_dir(),
 "safe_to_update_rag":False}
 report["safe_to_update_rag"]=all([report["nsis_rag_destination"],report["nsis_rag_recursive_copy"],report["source_has_rag_tool"]])
 return report
if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--source",type=Path,required=True)
 p.add_argument("--installed",type=Path,required=True)
 a=p.parse_args()
 report=check(a.source/"installer"/"CodeBridge.nsi",a.source,a.installed)
 print(json.dumps(report,indent=2))
 raise SystemExit(0 if report["safe_to_update_rag"] else 2)
