"""CPU-only model canary for RAG-016-C.

The canary deliberately forces llama.cpp to use --device none and -ngl 0.
It runs the pinned text and code models sequentially so a machine without a
dedicated GPU can exercise the full embedding backend without simultaneous
model residency.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import time
from typing import Optional, Tuple

from rag.models.artifact_install import resolve_selected_model_path
from rag.models.code_artifact_install import resolve_selected_code_model_path
from rag.models.code_backend_policy import CodeRetrievalTask
from rag.models.code_embedding import CodeEmbeddingClient
from rag.models.code_lifecycle import (
    CodeModelLifecycle,
    build_code_server_config,
)
from rag.models.embedding import TextEmbeddingClient
from rag.models.lifecycle import LlamaServerConfig, TextModelLifecycle
from rag.models.benchmark import windows_process_working_set_bytes


@dataclass(frozen=True)
class CpuModelCanaryResult:
    model: str
    pid: int
    dimension: int
    norm: float
    load_seconds: float
    embedding_ms: float
    unload_ms: float
    working_set_bytes: int
    nvidia_compute_present: Optional[bool]

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "pid": self.pid,
            "dimension": self.dimension,
            "norm": self.norm,
            "load_seconds": self.load_seconds,
            "embedding_ms": self.embedding_ms,
            "unload_ms": self.unload_ms,
            "working_set_bytes": self.working_set_bytes,
            "nvidia_compute_present": self.nvidia_compute_present,
        }


@dataclass(frozen=True)
class CpuOnlyCanaryResult:
    executable_path: str
    device: str
    gpu_layers: int
    text: CpuModelCanaryResult
    code: CpuModelCanaryResult

    def to_dict(self) -> dict[str, object]:
        return {
            "execution_mode": "CPU_ONLY",
            "executable_path": self.executable_path,
            "device": self.device,
            "gpu_layers": self.gpu_layers,
            "text": self.text.to_dict(),
            "code": self.code.to_dict(),
        }


def nvidia_compute_pids() -> Optional[Tuple[int, ...]]:
    """Return NVIDIA compute PIDs when nvidia-smi exists, otherwise None."""

    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if completed.returncode != 0:
        return None

    pids = []
    for line in (completed.stdout or "").splitlines():
        value = line.strip()
        if not value:
            continue
        try:
            pids.append(int(value))
        except ValueError:
            continue
    return tuple(sorted(set(pids)))


def _is_nvidia_compute_pid(pid: int) -> Optional[bool]:
    pids = nvidia_compute_pids()
    if pids is None:
        return None
    return pid in pids


def _text_cpu_config(
    executable_path: Path,
    model_path: Path,
) -> LlamaServerConfig:
    return LlamaServerConfig(
        executable_path=Path(executable_path),
        model_path=Path(model_path),
        gpu_layers=0,
        device="none",
    )


def _run_text_canary(
    executable_path: Path,
    model_path: Path,
) -> CpuModelCanaryResult:
    lifecycle = TextModelLifecycle(
        _text_cpu_config(executable_path, model_path)
    )
    loaded = None
    try:
        started = time.perf_counter()
        loaded = lifecycle.load(timeout_seconds=120)
        load_seconds = time.perf_counter() - started
        if loaded.pid is None:
            raise RuntimeError("text lifecycle reached READY without pid")

        client = TextEmbeddingClient(lifecycle)
        query_started = time.perf_counter()
        vector = client.embed_query(
            "CodeBridge CPU-only canary text retrieval"
        )
        embedding_ms = (
            time.perf_counter() - query_started
        ) * 1000.0

        pid = int(loaded.pid)
        working_set = windows_process_working_set_bytes(pid)
        in_nvidia = _is_nvidia_compute_pid(pid)

        unload_started = time.perf_counter()
        unloaded = lifecycle.unload(timeout_seconds=15)
        unload_ms = (
            time.perf_counter() - unload_started
        ) * 1000.0
        if unloaded.process_alive:
            raise RuntimeError("text model remained alive after unload")

        return CpuModelCanaryResult(
            model="jina-v5-text-small-retrieval",
            pid=pid,
            dimension=vector.dimension,
            norm=vector.norm,
            load_seconds=load_seconds,
            embedding_ms=embedding_ms,
            unload_ms=unload_ms,
            working_set_bytes=working_set,
            nvidia_compute_present=in_nvidia,
        )
    finally:
        if lifecycle.snapshot().process_alive:
            lifecycle.unload(timeout_seconds=15)


def _run_code_canary(
    executable_path: Path,
    model_path: Path,
) -> CpuModelCanaryResult:
    lifecycle = CodeModelLifecycle(
        build_code_server_config(
            executable_path=executable_path,
            model_path=model_path,
            gpu_layers=0,
            device="none",
        )
    )
    try:
        started = time.perf_counter()
        loaded = lifecycle.load(timeout_seconds=180)
        load_seconds = time.perf_counter() - started
        if loaded.pid is None:
            raise RuntimeError("code lifecycle reached READY without pid")

        client = CodeEmbeddingClient(lifecycle)
        query_started = time.perf_counter()
        vector = client.embed_query(
            CodeRetrievalTask.NL2CODE,
            "where is the cancellation flow implemented?",
        )
        embedding_ms = (
            time.perf_counter() - query_started
        ) * 1000.0

        pid = int(loaded.pid)
        working_set = windows_process_working_set_bytes(pid)
        in_nvidia = _is_nvidia_compute_pid(pid)

        unload_started = time.perf_counter()
        unloaded = lifecycle.unload(timeout_seconds=20)
        unload_ms = (
            time.perf_counter() - unload_started
        ) * 1000.0
        if unloaded.process_alive:
            raise RuntimeError("code model remained alive after unload")

        return CpuModelCanaryResult(
            model="jina-code-embeddings-1.5b",
            pid=pid,
            dimension=vector.dimension,
            norm=vector.norm,
            load_seconds=load_seconds,
            embedding_ms=embedding_ms,
            unload_ms=unload_ms,
            working_set_bytes=working_set,
            nvidia_compute_present=in_nvidia,
        )
    finally:
        if lifecycle.snapshot().process_alive:
            lifecycle.unload(timeout_seconds=20)


def run_cpu_only_canary(
    executable_path: str | Path,
) -> CpuOnlyCanaryResult:
    executable = Path(executable_path)
    text_path = resolve_selected_model_path()
    code_path = resolve_selected_code_model_path()

    text = _run_text_canary(
        executable,
        text_path,
    )
    code = _run_code_canary(
        executable,
        code_path,
    )

    if text.nvidia_compute_present is True:
        raise RuntimeError(
            "text CPU-only process unexpectedly appeared in NVIDIA compute"
        )
    if code.nvidia_compute_present is True:
        raise RuntimeError(
            "code CPU-only process unexpectedly appeared in NVIDIA compute"
        )

    return CpuOnlyCanaryResult(
        executable_path=str(executable),
        device="none",
        gpu_layers=0,
        text=text,
        code=code,
    )
