"""Fail-closed quality gate for a separately annotated RAG-017 holdout."""
from __future__ import annotations
import hashlib,json
from pathlib import Path

MIN_RECALL5=.80
MIN_RECALL10=.90
MIN_MRR=.60

def evaluate_holdout(questions_path:Path, labels_path:Path, predictions_path:Path, *, expected_sha256:str):
 raw=questions_path.read_bytes()
 digest=hashlib.sha256(raw).hexdigest()
 if digest != expected_sha256:raise ValueError("holdout questions digest mismatch")
 questions=[json.loads(x) for x in raw.decode("utf-8").splitlines() if x.strip()]
 labels=[json.loads(x) for x in labels_path.read_text(encoding="utf-8").splitlines() if x.strip()]
 predictions=[json.loads(x) for x in predictions_path.read_text(encoding="utf-8").splitlines() if x.strip()]
 def indexed(rows):
  ids=[r["id"] for r in rows]
  if len(ids)!=len(set(ids)):raise ValueError("duplicate IDs")
  return {r["id"]:r for r in rows}
 q,l,p=map(indexed,(questions,labels,predictions))
 if not q or set(q)!=set(l) or set(q)!=set(p):raise ValueError("incomplete evaluation set")
 ranks=[]
 for key in sorted(q):
  annotation=l[key]
  if annotation.get("review_status")!="INDEPENDENTLY_REVIEWED" or not annotation.get("reviewer_id"):
   raise ValueError("unverified holdout labels")
  paths=annotation.get("expected_paths")
  if not isinstance(paths,list) or not paths or not all(isinstance(x,str) and x for x in paths):
   raise ValueError("invalid ground truth")
  found=p[key].get("paths")
  if not isinstance(found,list) or len(found)!=len(set(found)) or not all(isinstance(x,str) for x in found):
   raise ValueError("invalid ranked results")
  rank=next((i for i,path in enumerate(found[:10],1) if path in paths),None)
  ranks.append(rank)
 n=len(ranks)
 r5=sum(v is not None and v<=5 for v in ranks)/n
 r10=sum(v is not None for v in ranks)/n
 mrr=sum(1/v for v in ranks if v is not None)/n
 return {"count":n,"recall_at_5":r5,"recall_at_10":r10,"mrr":mrr,"quality_passed":r5>=MIN_RECALL5 and r10>=MIN_RECALL10 and mrr>=MIN_MRR,"production_approved":False,"holdout_sha256":digest}
