"""Production readiness gate for the RAG-014 benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


GIB = 1024 ** 3


@dataclass(frozen=True)
class RagGoLiveThresholds:
    recall_at_5_min: float = 0.80
    recall_at_10_min: float = 0.90
    mrr_min: float = 0.60
    cold_latency_ms_max: float = 20_000.0
    warm_p95_ms_max: float = 1_000.0
    ram_peak_bytes_max: int = 6 * GIB
    vram_delta_mib_max: int = 5_120
    index_size_bytes_max: int = 2 * GIB


@dataclass(frozen=True)
class RagGoLiveObservation:
    production_index_ready: bool
    semantic_metrics_available: bool
    recall_at_5: Optional[float] = None
    recall_at_10: Optional[float] = None
    mrr: Optional[float] = None
    cold_latency_ms: Optional[float] = None
    warm_p95_ms: Optional[float] = None
    ram_peak_bytes: Optional[int] = None
    vram_delta_mib: Optional[int] = None
    index_size_bytes: Optional[int] = None


@dataclass(frozen=True)
class RagGoLiveDecision:
    passed: bool
    failed_checks: Tuple[str, ...]
    thresholds: RagGoLiveThresholds

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "failed_checks": list(self.failed_checks),
            "thresholds": {
                "recall_at_5_min": self.thresholds.recall_at_5_min,
                "recall_at_10_min": self.thresholds.recall_at_10_min,
                "mrr_min": self.thresholds.mrr_min,
                "cold_latency_ms_max": self.thresholds.cold_latency_ms_max,
                "warm_p95_ms_max": self.thresholds.warm_p95_ms_max,
                "ram_peak_bytes_max": self.thresholds.ram_peak_bytes_max,
                "vram_delta_mib_max": self.thresholds.vram_delta_mib_max,
                "index_size_bytes_max": self.thresholds.index_size_bytes_max,
            },
        }


def _minimum(
    name: str,
    value: Optional[float],
    threshold: float,
    failures: list[str],
) -> None:
    if value is None:
        failures.append(f"{name}:NOT_MEASURED")
    elif float(value) < threshold:
        failures.append(
            f"{name}:BELOW_THRESHOLD:{float(value):.6f}<{threshold:.6f}"
        )


def _maximum(
    name: str,
    value: Optional[float | int],
    threshold: float | int,
    failures: list[str],
) -> None:
    if value is None:
        failures.append(f"{name}:NOT_MEASURED")
    elif float(value) > float(threshold):
        failures.append(
            f"{name}:ABOVE_THRESHOLD:{float(value):.6f}>{float(threshold):.6f}"
        )


def evaluate_go_live(
    observation: RagGoLiveObservation,
    *,
    thresholds: RagGoLiveThresholds = RagGoLiveThresholds(),
) -> RagGoLiveDecision:
    if not isinstance(observation, RagGoLiveObservation):
        raise ValueError("observation must be RagGoLiveObservation")
    if not isinstance(thresholds, RagGoLiveThresholds):
        raise ValueError("thresholds must be RagGoLiveThresholds")

    failures: list[str] = []

    if not observation.production_index_ready:
        failures.append("production_index:NOT_READY")
    if not observation.semantic_metrics_available:
        failures.append("semantic_metrics:NOT_AVAILABLE")

    _minimum(
        "recall_at_5",
        observation.recall_at_5,
        thresholds.recall_at_5_min,
        failures,
    )
    _minimum(
        "recall_at_10",
        observation.recall_at_10,
        thresholds.recall_at_10_min,
        failures,
    )
    _minimum(
        "mrr",
        observation.mrr,
        thresholds.mrr_min,
        failures,
    )
    _maximum(
        "cold_latency_ms",
        observation.cold_latency_ms,
        thresholds.cold_latency_ms_max,
        failures,
    )
    _maximum(
        "warm_p95_ms",
        observation.warm_p95_ms,
        thresholds.warm_p95_ms_max,
        failures,
    )
    _maximum(
        "ram_peak_bytes",
        observation.ram_peak_bytes,
        thresholds.ram_peak_bytes_max,
        failures,
    )
    _maximum(
        "vram_delta_mib",
        observation.vram_delta_mib,
        thresholds.vram_delta_mib_max,
        failures,
    )
    _maximum(
        "index_size_bytes",
        observation.index_size_bytes,
        thresholds.index_size_bytes_max,
        failures,
    )

    return RagGoLiveDecision(
        passed=not failures,
        failed_checks=tuple(failures),
        thresholds=thresholds,
    )
