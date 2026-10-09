"""Reject exact normalized question leakage from previously used RAG benchmarks."""
import argparse,json,re,hashlib
from pathlib import Path

def norm(value):
 if not isinstance(value,str) or not value.strip():raise ValueError("question text required")
 return re.sub(r"\s+"," ",value.casefold().strip())

def rows(path):
 items=[json.loads(line) for line in path.read_text(encoding="utf8").splitlines() if line.strip()]
 if not items:raise ValueError("empty dataset")
 return items

def check(candidate, known_files):
 proposed=rows(candidate)
 known={}
 for file in known_files:
  for row in rows(file):
   if "query" in row:
    known.setdefault(norm(row["query"]),[]).append(str(file))
 seen=set();collisions=[]
 for row in proposed:
  key=norm(row["query"])
  if key in seen:collisions.append({"id":row.get("id"),"reason":"duplicate_candidate"})
  seen.add(key)
  if key in known:collisions.append({"id":row.get("id"),"reason":"known_question","sources":known[key]})
 return {"candidate_sha256":hashlib.sha256(candidate.read_bytes()).hexdigest(),"candidate_count":len(proposed),"known_file_count":len(known_files),"exact_collisions":collisions,"exact_overlap_pass":not collisions,"independence_certified":False}

if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("candidate",type=Path)
 p.add_argument("known",type=Path,nargs="+")
 args=p.parse_args()
 report=check(args.candidate,args.known)
 print(json.dumps(report,indent=2))
 raise SystemExit(0 if report["exact_overlap_pass"] else 1)
