"""Conservative semantic-overlap triage; never certifies independence."""
import argparse,json,re
from pathlib import Path
from difflib import SequenceMatcher
from benchmarks.audit_rag017_holdout_overlap import rows,norm

def tokens(text):
 return set(re.findall(r"\w+",norm(text),flags=re.UNICODE))

def screen(candidate,known_files,threshold=.78):
 if not 0<threshold<=1:raise ValueError("threshold outside (0,1]")
 source=[]
 for file in known_files:
  for row in rows(file):
   if isinstance(row.get("query"),str):
    source.append((str(file),row.get("id"),norm(row["query"])))
 flags=[]
 for item in rows(candidate):
  query=norm(item["query"])
  qt=tokens(query)
  for file,key,old in source:
   ot=tokens(old)
   jac=len(qt&ot)/len(qt|ot) if qt|ot else 0
   seq=SequenceMatcher(None,query,old).ratio()
   score=max(jac,seq)
   if score>=threshold:
    flags.append({"candidate_id":item.get("id"),"known_id":key,"source":file,"similarity":round(score,4)})
 return {"flagged_pairs":flags,"requires_manual_review":bool(flags),"independence_certified":False,"warning":"heuristic lexical/sequence similarity; unflagged paraphrases may remain"}

if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("candidate",type=Path)
 p.add_argument("known",type=Path,nargs="+")
 p.add_argument("--threshold",type=float,default=.78)
 a=p.parse_args()
 print(json.dumps(screen(a.candidate,a.known,a.threshold),indent=2))
