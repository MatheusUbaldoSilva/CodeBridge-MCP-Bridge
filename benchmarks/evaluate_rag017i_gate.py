"""RAG-017-I: immutable threshold qualification using frozen benchmark and live index."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from rag.runtime.status import build_rag_status
from rag.index.manifest import load_index_manifest

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/"benchmarks"
def read(name): return json.loads((B/name).read_text(encoding="utf-8"))
frozen=read("rag014_readiness_report.json")
replay=read("rag017f_semantic_latest.json")
floor=frozen["decision"]["thresholds"]
index=build_rag_status().index
assert index["state"]=="READY"
manifest=load_index_manifest(index["manifest_path"])
db=Path(index["sqlite_path"])
qdrant=Path(index["qdrant_path"])
conn=sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro",uri=True)
try:
    integrity=conn.execute("PRAGMA integrity_check").fetchone()[0]
    document_count=conn.execute("SELECT count(*) FROM rag_documents").fetchone()[0]
    chunk_count=conn.execute("SELECT count(*) FROM rag_chunks").fetchone()[0]
finally: conn.close()
assert integrity=="ok"
assert document_count==len(manifest.entries)==210
assert chunk_count==8761
total_size=db.stat().st_size + sum(p.stat().st_size for p in qdrant.rglob("*") if p.is_file())+Path(index["manifest_path"]).stat().st_size
observed={
    "recall_at_5":replay["metrics"]["recall_at_5"],
    "recall_at_10":replay["metrics"]["recall_at_10"],
    "mrr":replay["metrics"]["mrr"],
    "cold_latency_ms":replay["latency"]["cold_estimate_ms"],
    "warm_p95_ms":replay["latency"]["warm_p95_ms"],
    "ram_peak_bytes":replay["resources"]["python_rss_bytes"]+replay["resources"]["llama_peak_rss_bytes"],
    "vram_delta_mib":replay["resources"]["max_vram_delta_mib"],
    "index_size_bytes":replay["resources"]["total_index_size_bytes"],
}
checks={
    "recall_at_5":{"measured":observed["recall_at_5"],"limit":floor["recall_at_5_min"],"passed":observed["recall_at_5"]>=floor["recall_at_5_min"],"source":"RAG-017-F real semantic benchmark"},
    "recall_at_10":{"measured":observed["recall_at_10"],"limit":floor["recall_at_10_min"],"passed":observed["recall_at_10"]>=floor["recall_at_10_min"],"source":"RAG-017-F real semantic benchmark"},
    "mrr":{"measured":observed["mrr"],"limit":floor["mrr_min"],"passed":observed["mrr"]>=floor["mrr_min"],"source":"RAG-017-F real semantic benchmark"},
    "cold_latency_ms":{"measured":observed["cold_latency_ms"],"limit":floor["cold_latency_ms_max"],"passed":observed["cold_latency_ms"]<=floor["cold_latency_ms_max"],"source":"RAG-017-F estimated cold latency"},
    "warm_p95_ms":{"measured":observed["warm_p95_ms"],"limit":floor["warm_p95_ms_max"],"passed":observed["warm_p95_ms"]<=floor["warm_p95_ms_max"],"source":"RAG-017-F benchmark"},
    "ram_peak_bytes":{"measured":observed["ram_peak_bytes"],"limit":floor["ram_peak_bytes_max"],"passed":observed["ram_peak_bytes"]<=floor["ram_peak_bytes_max"],"source":"RAG-017-F sum of recorded python and llama RSS; approximate"},
    "vram_delta_mib":{"measured":observed["vram_delta_mib"],"limit":floor["vram_delta_mib_max"],"passed":observed["vram_delta_mib"]<=floor["vram_delta_mib_max"],"source":"RAG-017-F benchmark"},
    "index_size_bytes":{"measured":observed["index_size_bytes"],"limit":floor["index_size_bytes_max"],"passed":observed["index_size_bytes"]<=floor["index_size_bytes_max"],"source":"RAG-017-F temporary index"},
    "persistent_index_size_bytes":{"measured":total_size,"limit":floor["index_size_bytes_max"],"passed":total_size<=floor["index_size_bytes_max"],"source":"live published SQLite + Qdrant + manifest"},
}
result={"stage":"RAG-017-I","production_gate":"PASS" if all(x["passed"] for x in checks.values()) else "BLOCKED","checks":checks,"threshold_source":"benchmarks/rag014_readiness_report.json","quality_benchmark":"benchmarks/rag017f_semantic_latest.json","persistent":{"state":index["state"],"documents":document_count,"chunks":chunk_count,"manifest_entries":len(manifest.entries),"sqlite_integrity":integrity},"limitations":["cold is benchmark estimate, not independent restart load timer","RAM uses approximate RSS sum","quality metrics derived from temporary benchmark corpus; persistent corpus differs","application installed MCP not activated and continuous reindex not enabled"]}
(B/"rag017i_production_gate.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"production_gate":result["production_gate"],"checks":checks,"persistent":result["persistent"]},ensure_ascii=False,indent=2))
