"""Disposable Qdrant backup/restore integrity probe (closed database only)."""
import argparse,hashlib,json,shutil
from pathlib import Path
from qdrant_client import QdrantClient,models
p=argparse.ArgumentParser()
p.add_argument("--root",type=Path,required=True)
a=p.parse_args()
root=a.root.resolve()
if not root.name.startswith("CodeBridge-RAG017-BackupProbe-") or root.parent.name.lower()!="temp" or root.exists():raise SystemExit("unsafe or existing probe root")
root.mkdir()
db=root/"live";backup=root/"backup";restored=root/"restored"
client=QdrantClient(path=str(db))
client.create_collection("canary",vectors_config=models.VectorParams(size=4,distance=models.Distance.COSINE))
client.upsert("canary",[models.PointStruct(id=47,vector=[1,0,0,0],payload={"marker":"isolated-backup"})],wait=True)
client.close()
shutil.copytree(db,backup)
def manifest(path):
 return {str(p.relative_to(path)).replace("\\","/"):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob("*") if p.is_file()}
original=manifest(db);copied=manifest(backup)
if original!=copied:raise SystemExit("backup mismatch")
shutil.copytree(backup,restored)
recovered=QdrantClient(path=str(restored))
items=recovered.retrieve("canary",[47],with_payload=True)
ok=len(items)==1 and items[0].payload.get("marker")=="isolated-backup" and recovered.count("canary",exact=True).count==1
recovered.close()
print(json.dumps({"backup_files":len(copied),"hash_identical":original==copied,"restore_read_ok":ok,"isolated":True}))
if not ok:raise SystemExit(2)
