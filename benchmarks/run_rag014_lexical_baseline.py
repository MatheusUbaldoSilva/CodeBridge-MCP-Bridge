from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.benchmark.corpus import build_lexical_benchmark_index, lexical_ranked_paths
from rag.benchmark.metrics import (
    current_process_rss_bytes,
    current_vram_used_mib,
    directory_size_bytes,
    evaluate_ranked_paths,
)


DATASET = ROOT / "benchmarks" / "rag014_dataset.jsonl"
GROUND_TRUTH = ROOT / "benchmarks" / "rag014_ground_truth.jsonl"
OUTPUT = ROOT / "benchmarks" / "rag014_lexical_baseline_latest.json"


def load_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    dataset = load_jsonl(DATASET)
    truth_rows = load_jsonl(GROUND_TRUTH)
    truth = {
        row["id"]: tuple(row["expected_paths"])
        for row in truth_rows
    }

    with tempfile.TemporaryDirectory(prefix="codebridge-rag014-") as td:
        db = Path(td) / "rag014.sqlite3"

        build_started = time.perf_counter()
        stats = build_lexical_benchmark_index(ROOT, db)
        build_ms = (time.perf_counter() - build_started) * 1000.0

        connection = sqlite3.connect(str(db))
        try:
            first = dataset[0]
            cold_started = time.perf_counter()
            lexical_ranked_paths(
                connection,
                first["query"],
                top_k=10,
            )
            cold_query_ms = (
                time.perf_counter() - cold_started
            ) * 1000.0

            ranked = {}
            warm_samples = []
            for row in dataset:
                started = time.perf_counter()
                ranked[row["id"]] = lexical_ranked_paths(
                    connection,
                    row["query"],
                    top_k=10,
                )
                warm_samples.append(
                    (time.perf_counter() - started) * 1000.0
                )

            metrics = evaluate_ranked_paths(ranked, truth)
            payload = {
                "benchmark": "RAG-014-C_LEXICAL_BASELINE",
                "scope": "LEXICAL_ONLY",
                "query_count": len(dataset),
                "corpus": {
                    "documents": stats.documents,
                    "chunks": stats.chunks,
                    "denied": stats.denied,
                    "unsupported": stats.unsupported,
                },
                "metrics": metrics.to_dict(),
                "latency": {
                    "index_build_ms": build_ms,
                    "cold_query_ms": cold_query_ms,
                    "warm_query_mean_ms": statistics.fmean(warm_samples),
                    "warm_query_median_ms": statistics.median(warm_samples),
                    "warm_query_p95_ms": sorted(warm_samples)[
                        max(0, int(len(warm_samples) * 0.95) - 1)
                    ],
                },
                "resources": {
                    "ram_rss_bytes": current_process_rss_bytes(),
                    "vram_device_used_mib": current_vram_used_mib(),
                    "index_size_bytes": directory_size_bytes(db),
                },
                "limitations": [
                    "lexical baseline only",
                    "does not measure text/code semantic embeddings",
                    "does not satisfy final RAG-014-C hybrid metric requirement",
                ],
            }
            rendered = json.dumps(payload, indent=2, ensure_ascii=False)
            OUTPUT.write_text(rendered + "\n", encoding="utf-8")
            print(rendered)
        finally:
            connection.close()


if __name__ == "__main__":
    main()
