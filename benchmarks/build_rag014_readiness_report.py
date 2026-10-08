from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.benchmark.gate import (
    RagGoLiveObservation,
    RagGoLiveThresholds,
    evaluate_go_live,
)
from rag.runtime.status import build_rag_status


SEMANTIC = ROOT / "benchmarks" / "rag014_semantic_benchmark_latest.json"
LEXICAL = ROOT / "benchmarks" / "rag014_lexical_baseline_latest.json"
OUTPUT = ROOT / "benchmarks" / "rag014_readiness_report.json"


def main() -> None:
    semantic = json.loads(SEMANTIC.read_text(encoding="utf-8"))
    lexical = json.loads(LEXICAL.read_text(encoding="utf-8"))
    status = build_rag_status().to_dict()
    index_ready = status["index"].get("state") == "READY"

    semantic_metrics = semantic["metrics"]
    latency = semantic["latency"]
    resources = semantic["resources"]
    ram_peak = (
        int(resources["llama_peak_rss_bytes"])
        + int(resources["python_rss_bytes"])
    )

    observation = RagGoLiveObservation(
        production_index_ready=index_ready,
        semantic_metrics_available=True,
        recall_at_5=float(semantic_metrics["recall_at_5"]),
        recall_at_10=float(semantic_metrics["recall_at_10"]),
        mrr=float(semantic_metrics["mrr"]),
        cold_latency_ms=float(latency["cold_estimate_ms"]),
        warm_p95_ms=float(latency["warm_p95_ms"]),
        ram_peak_bytes=ram_peak,
        vram_delta_mib=int(resources["max_vram_delta_mib"]),
        index_size_bytes=int(resources["total_index_size_bytes"]),
    )
    thresholds = RagGoLiveThresholds()
    decision = evaluate_go_live(
        observation,
        thresholds=thresholds,
    )

    payload = {
        "benchmark": "RAG-014",
        "production_readiness": "PASS" if decision.passed else "BLOCKED",
        "decision": decision.to_dict(),
        "production_index": status["index"],
        "models": status["models"],
        "backend": status["backend"],
        "semantic_metrics": semantic,
        "lexical_control": lexical,
        "interpretation": [
            "The semantic benchmark is measured with real local models, FTS5, Qdrant Local, RRF and deduplication.",
            "The production index state is evaluated independently from the temporary benchmark index.",
            "Go-live is allowed only if every frozen threshold and the production-index readiness check pass.",
        ],
    }
    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    OUTPUT.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
