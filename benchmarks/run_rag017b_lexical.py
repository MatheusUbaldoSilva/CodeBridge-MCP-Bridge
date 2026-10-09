"""RAG-017-B lexical recall measurement on the frozen 100-query dataset."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rag.benchmark.corpus import build_lexical_benchmark_index
from rag.contracts import SearchQuery
from rag.index.lexical_ranking import search_lexical_ranked
from rag.benchmark.metrics import evaluate_ranked_paths
from rag.runtime.query_classifier import classify_query
import tempfile,sqlite3
bench=ROOT/"benchmarks"
q=[json.loads(s) for s in (bench/"rag014_dataset.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
g=[json.loads(s) for s in (bench/"rag014_ground_truth.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
expected={r["id"]:r["expected_paths"] for r in g}
with tempfile.TemporaryDirectory(prefix="rag017b-lexical-") as td:
    path=Path(td)/"lex.sqlite3"
    corpus=build_lexical_benchmark_index(ROOT,path)
    conn=sqlite3.connect(str(path))
    try:
        ranked={}
        for row in q:
            query=SearchQuery(query=row["query"],project_id="codebridge",top_k=10)
            results=search_lexical_ranked(conn,query)
            ranked[row["id"]]=[r.metadata.path or "" for r in results]
        metrics=evaluate_ranked_paths(ranked,expected)
        out={"stage":"RAG-017-B","corpus":{"documents":corpus.documents,"chunks":corpus.chunks},"metrics":metrics.to_dict(),"top10_paths":ranked}
        (bench/"rag017b_lexical_latest.json").write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        print(json.dumps({"metrics":out["metrics"],"corpus":out["corpus"]},indent=2))
    finally:conn.close()
