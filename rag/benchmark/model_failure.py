"""Deliberate model-failure canary for RAG-016-E."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
import time
from typing import Tuple

from rag.models.code_lifecycle import (
    CodeModelLifecycle,
    build_code_server_config,
)
from rag.models.lifecycle import (
    LlamaServerConfig,
    ModelLifecycleState,
    ModelLoadError,
    TextModelLifecycle,
)


@dataclass(frozen=True)
class FailedModelProbe:
    model_kind: str
    expected_error: str
    elapsed_ms: float
    final_state: str
    process_alive: bool
    pid: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            "model_kind": self.model_kind,
            "expected_error": self.expected_error,
            "elapsed_ms": self.elapsed_ms,
            "final_state": self.final_state,
            "process_alive": self.process_alive,
            "pid": self.pid,
        }


@dataclass(frozen=True)
class ModelFailureCanaryResult:
    executable_path: str
    failures: Tuple[FailedModelProbe, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "benchmark": "RAG-016-E_MODEL_FAILURE",
            "executable_path": self.executable_path,
            "failure_count": len(self.failures),
            "failures": [item.to_dict() for item in self.failures],
        }


def _expect_load_failure(
    lifecycle,
    *,
    model_kind: str,
) -> FailedModelProbe:
    started = time.perf_counter()
    try:
        lifecycle.load(timeout_seconds=10)
    except ModelLoadError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        snapshot = lifecycle.snapshot()
        if snapshot.state is not ModelLifecycleState.UNLOADED:
            raise RuntimeError(
                f"{model_kind} failure did not return lifecycle to UNLOADED"
            )
        if snapshot.process_alive:
            raise RuntimeError(
                f"{model_kind} failure left a model process alive"
            )
        return FailedModelProbe(
            model_kind=model_kind,
            expected_error=str(exc),
            elapsed_ms=elapsed_ms,
            final_state=snapshot.state.value,
            process_alive=snapshot.process_alive,
            pid=snapshot.pid,
        )
    raise RuntimeError(
        f"{model_kind} unexpectedly loaded a deliberately missing model"
    )


def run_model_failure_canary(
    executable_path: str | Path,
) -> ModelFailureCanaryResult:
    executable = Path(executable_path)

    with tempfile.TemporaryDirectory(
        prefix="codebridge-rag016-model-failure-"
    ) as td:
        missing_text = Path(td) / "missing-text.gguf"
        missing_code = Path(td) / "missing-code.gguf"

        text = TextModelLifecycle(
            LlamaServerConfig(
                executable_path=executable,
                model_path=missing_text,
                device="none",
                gpu_layers=0,
            )
        )
        code = CodeModelLifecycle(
            build_code_server_config(
                executable_path=executable,
                model_path=missing_code,
                device="none",
                gpu_layers=0,
            )
        )

        failures = (
            _expect_load_failure(
                text,
                model_kind="TEXT",
            ),
            _expect_load_failure(
                code,
                model_kind="CODE",
            ),
        )

    return ModelFailureCanaryResult(
        executable_path=str(executable),
        failures=failures,
    )
