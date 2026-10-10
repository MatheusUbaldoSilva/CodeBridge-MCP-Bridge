"""RAG-017: isolated Qdrant local persistence probe (two separate invocations)."""
import argparse,json,hashlib
from pathlib import Path
from qdrant_client import QdrantClient,models
p=argparse.ArgumentParser();p.add_argument("phase",choices=("write","read"));p.add_argument("--dir",type=Path,required=True);a=p.parse_args()
if "CodeBridge-RAG017-Qdrant-Probe-" not in str(a.dir):raise SystemExit("unsafe storage path")
coll="rag017_persistence_canary"; vec=[1.0,0.0,0.0,0.0]
if a.phase=="write":
 if a.dir.exists():raise SystemExit("refusing existing storage")
 a.dir.mkdir(parents=True)
 c=QdrantClient(path=str(a.dir))
 c.create_collection(collection_name=coll,vectors_config=models.VectorParams(size=4,distance=models.Distance.COSINE))
 c.upsert(collection_name=coll,points=[models.PointStruct(id=17,vector=vec,payload={"marker":"rag017-isolated-only","project_id":"codebridge"})],wait=True)
 print(json.dumps({"phase":"write","count":c.count(coll,exact=True).count,"storage":str(a.dir)}))
 c.close()
else:
 if not a.dir.exists():raise SystemExit("missing storage")
 c=QdrantClient(path=str(a.dir))
 r=c.retrieve(collection_name=coll,ids=[17],with_payload=True,with_vectors=True)
 ok=len(r)==1 and r[0].payload.get("marker")=="rag017-isolated-only" and c.count(coll,exact=True).count==1
 print(json.dumps({"phase":"read","count":c.count(coll,exact=True).count,"payload":r[0].payload if r else None,"passed":ok}))
 c.close()
 if not ok:raise SystemExit(2)
