"""Benchmark helpers for CodeBridge RAG."""

from .corpus import (
    BenchmarkCorpusStats,
    DEFAULT_BENCHMARK_PATHS,
    build_lexical_benchmark_index,
    lexical_ranked_paths,
)
from .gate import (
    RagGoLiveDecision,
    RagGoLiveObservation,
    RagGoLiveThresholds,
    evaluate_go_live,
)
from .metrics import (
    ResourceSnapshot,
    RetrievalMetrics,
    capture_resource_snapshot,
    current_process_rss_bytes,
    current_vram_used_mib,
    process_rss_bytes,
    directory_size_bytes,
    evaluate_ranked_paths,
    measure_latency_ms,
)

__all__ = [
    "BenchmarkCorpusStats",
    "DEFAULT_BENCHMARK_PATHS",
    "build_lexical_benchmark_index",
    "lexical_ranked_paths",
    "RagGoLiveDecision",
    "RagGoLiveObservation",
    "RagGoLiveThresholds",
    "evaluate_go_live",
    "ResourceSnapshot",
    "RetrievalMetrics",
    "capture_resource_snapshot",
    "current_process_rss_bytes",
    "current_vram_used_mib",
    "process_rss_bytes",
    "directory_size_bytes",
    "evaluate_ranked_paths",
    "measure_latency_ms",
]
