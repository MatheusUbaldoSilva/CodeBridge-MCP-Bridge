"""Disposable Qdrant crash/reopen experiment; never touch production storage."""
import argparse,json,time
from pathlib import Path
from qdrant_client import QdrantClient,models
p=argparse.ArgumentParser();p.add_argument("mode",choices=("hold","recover"));p.add_argument("--path",required=True,type=Path);a=p.parse_args()
path=a.path.resolve()
if not path.name.startswith("CodeBridge-RAG017-CrashProbe-") or path.parent.name.lower()!="temp":
 raise SystemExit("unsafe test location: require direct TEMP staging directory")
name="crash_probe"
if a.mode=="hold":
 if path.exists(): raise SystemExit("refusing existing storage")
 path.mkdir()
 client=QdrantClient(path=str(path))
 client.create_collection(name,vectors_config=models.VectorParams(size=4,distance=models.Distance.COSINE))
 client.upsert(name,[models.PointStruct(id=71,vector=[1,0,0,0],payload={"canary":"after-abrupt-kill"})],wait=True)
 print(json.dumps({"ready_to_kill":True,"count":client.count(name,exact=True).count}),flush=True)
 time.sleep(120)
else:
 if not path.exists():raise SystemExit("missing storage")
 client=QdrantClient(path=str(path))
 points=client.retrieve(name,[71],with_payload=True)
 success=len(points)==1 and points[0].payload.get("canary")=="after-abrupt-kill" and client.count(name,exact=True).count==1
 print(json.dumps({"recovered":success,"count":client.count(name,exact=True).count}),flush=True)
 client.close()
 if not success:raise SystemExit(2)
