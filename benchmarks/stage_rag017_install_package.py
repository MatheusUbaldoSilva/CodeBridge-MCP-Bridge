"""Read-only validation of RAG files in an isolated release staging directory."""
import argparse,json,shutil,tempfile
from pathlib import Path

def stage(source, destination):
 source=Path(source); destination=Path(destination)
 if destination.exists():raise FileExistsError("refusing to overwrite staging directory")
 if not (source/"rag"/"__init__.py").is_file():raise FileNotFoundError("source RAG package missing")
 destination.mkdir(parents=True)
 for name in ("rag","author_mcp"):
  source_dir=source/name
  shutil.copytree(source_dir,destination/name,ignore=shutil.ignore_patterns("__pycache__","*.pyc",".venv","*.log","*.db","*.sqlite*"),dirs_exist_ok=False)
 (destination/"installer").mkdir()
 shutil.copy2(source/"installer"/"bootstrap.ps1",destination/"installer"/"bootstrap.ps1")
 files=[f for f in (destination/"rag").rglob("*.py")]
 result={"rag_python_files":len(files),"mcp_file_present":(destination/"author_mcp"/"mcp_server.py").is_file(),"rag_package_present":(destination/"rag"/"__init__.py").is_file(),"staged":True,"installed":False,"production_approved":False}
 (destination/"staging_report.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
 return result

if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--source",type=Path,required=True)
 p.add_argument("--destination",type=Path,required=True)
 a=p.parse_args()
 print(json.dumps(stage(a.source,a.destination),indent=2))
