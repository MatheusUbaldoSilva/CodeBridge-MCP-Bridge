"""Blindly generate ranked predictions from a frozen questions-only JSONL file.

No ground-truth labels are opened by this runner. Production remains unchanged.
"""
import argparse,hashlib,json,time
from pathlib import Path
from unittest.mock import patch
from rag.contracts import SearchQuery
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.resident_models import resident_pool
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local

def run(questions, predictions, manifest, expected_sha256):
 raw=questions.read_bytes()
 actual=hashlib.sha256(raw).hexdigest()
 if actual!=expected_sha256:raise ValueError("frozen questions SHA-256 mismatch")
 rows=[json.loads(line) for line in raw.decode("utf8").splitlines() if line.strip()]
 if not rows or len({row["id"] for row in rows})!=len(rows):raise ValueError("missing or duplicate questions")
 if not all(isinstance(row.get("query"),str) and row["query"].strip() for row in rows):raise ValueError("invalid question")
 if predictions.exists() or manifest.exists():raise FileExistsError("refuse to overwrite previous evaluation artifacts")
 client=open_qdrant_local()
 outputs=[]
 started=time.perf_counter()
 try:
  with patch.dict(search_persistent_semantic.__globals__,{"open_qdrant_local":lambda *a,**kw:client,"close_qdrant_local":lambda c:None}):
   for item in rows:
    hits=search_persistent_semantic(SearchQuery(query=item["query"],project_id="codebridge",top_k=10),QueryRoute.CODE,experimental_cross_route=True,experimental_resident_models=True)
    outputs.append({"id":item["id"],"paths":[h.metadata.path for h in hits]})
 finally:
  resident_pool.close()
  close_qdrant_local(client)
 encoded="".join(json.dumps(row,ensure_ascii=False)+"\n" for row in outputs)
 predictions.write_text(encoded,encoding="utf8")
 manifest.write_text(json.dumps({"questions_sha256":actual,"predictions_sha256":hashlib.sha256(predictions.read_bytes()).hexdigest(),"query_count":len(rows),"model_route":"CODE","experimental":True,"seconds":round(time.perf_counter()-started,3),"production_approved":False},indent=2)+"\n",encoding="utf8")

if __name__=="__main__":
 parser=argparse.ArgumentParser()
 parser.add_argument("--questions",type=Path,required=True)
 parser.add_argument("--predictions",type=Path,required=True)
 parser.add_argument("--manifest",type=Path,required=True)
 parser.add_argument("--sha256",required=True)
 args=parser.parse_args()
 run(args.questions,args.predictions,args.manifest,args.sha256)
