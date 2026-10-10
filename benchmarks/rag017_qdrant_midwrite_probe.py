"""Isolated Qdrant batch-interruption canary. No production collections."""
import argparse,json,time
from pathlib import Path
from qdrant_client import QdrantClient,models
p=argparse.ArgumentParser();p.add_argument("phase",choices=("write","check"));p.add_argument("--dir",type=Path,required=True);a=p.parse_args()
root=a.dir.resolve()
if not root.name.startswith("CodeBridge-RAG017-MidWrite-") or root.parent.name.lower()!="temp":raise SystemExit("unsafe path")
coll="midwrite_canary"
if a.phase=="write":
 if root.exists():raise SystemExit("refusing existing directory")
 root.mkdir()
 c=QdrantClient(path=str(root))
 c.create_collection(coll,vectors_config=models.VectorParams(size=4,distance=models.Distance.COSINE))
 c.upsert(coll,[models.PointStruct(id=1,vector=[1,0,0,0],payload={"committed":True})],wait=True)
 print(json.dumps({"baseline_committed":True,"count":c.count(coll,exact=True).count}),flush=True)
 for i in range(2,100002):
  c.upsert(coll,[models.PointStruct(id=i,vector=[1,0,0,0],payload={"batch":i})],wait=True)
  if i%100==0:print(json.dumps({"progress":i}),flush=True)
else:
 c=QdrantClient(path=str(root))
 baseline=c.retrieve(coll,[1],with_payload=True)
 count=c.count(coll,exact=True).count
 passed=len(baseline)==1 and baseline[0].payload.get("committed") is True
 print(json.dumps({"baseline_intact":passed,"surviving_count":count,"partial_batch_expected":True}),flush=True)
 c.close()
 if not passed:raise SystemExit(2)
