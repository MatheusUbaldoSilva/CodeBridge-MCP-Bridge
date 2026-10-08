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
from .soak import (
    SoakResult,
    run_storage_retrieval_soak,
)
from .restart import (
    RESTART_BASELINE_FILENAME,
    RestartProbe,
    prepare_restart_probe,
    verify_restart_probe,
)
from .cpu_canary import (
    CpuModelCanaryResult,
    CpuOnlyCanaryResult,
    nvidia_compute_pids,
    run_cpu_only_canary,
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
    "SoakResult",
    "run_storage_retrieval_soak",
    "RESTART_BASELINE_FILENAME",
    "RestartProbe",
    "prepare_restart_probe",
    "verify_restart_probe",
    "CpuModelCanaryResult",
    "CpuOnlyCanaryResult",
    "nvidia_compute_pids",
    "run_cpu_only_canary",
]
