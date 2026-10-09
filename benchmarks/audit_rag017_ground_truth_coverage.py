"""Find frozen benchmark expected sources absent in the live index."""
import json,sqlite3
from pathlib import Path
from rag.runtime.status import resolve_rag_sqlite_path
B=Path(__file__).resolve().parents[1]/"benchmarks"
gt=[json.loads(s) for s in (B/"rag014_ground_truth.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
conn=sqlite3.connect(f"{resolve_rag_sqlite_path().resolve().as_uri()}?mode=ro",uri=True)
try:
 paths=set(x[0] for x in conn.execute("SELECT DISTINCT path FROM rag_documents"))
finally:conn.close()
missing=[]
for x in gt:
 if not any(path in paths for path in x["expected_paths"]):
  missing.append({"id":x["id"],"expected_paths":x["expected_paths"]})
report={"expected_fully_absent_queries":len(missing),"missing":missing,"index_paths":len(paths)}
(B/"rag017_ground_truth_coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2))
