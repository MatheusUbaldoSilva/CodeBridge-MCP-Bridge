"""GPU production canary for RAG-016-D."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Optional, Tuple

from rag.benchmark.cpu_canary import nvidia_compute_pids
from rag.benchmark.metrics import current_vram_used_mib
from rag.models.artifact_install import resolve_selected_model_path
from rag.models.code_artifact_install import resolve_selected_code_model_path
from rag.models.code_backend_policy import CodeRetrievalTask
from rag.models.code_embedding import CodeEmbeddingClient
from rag.models.code_lifecycle import (
    CodeModelLifecycle,
    build_code_server_config,
)
from rag.models.embedding import TextEmbeddingClient
from rag.models.fallback import (
    build_gpu_config,
    discover_llama_devices,
)
from rag.models.lifecycle import LlamaServerConfig, TextModelLifecycle
from rag.models.benchmark import windows_process_working_set_bytes


@dataclass(frozen=True)
class GpuModelCanaryResult:
    model: str
    device: str
    gpu_layers: int
    pid: int
    dimension: int
    norm: float
    load_seconds: float
    embedding_ms: float
    unload_ms: float
    working_set_bytes: int
    nvidia_compute_present: Optional[bool]
    vram_before_mib: Optional[int]
    vram_loaded_mib: Optional[int]
    vram_after_mib: Optional[int]
    vram_delta_mib: Optional[int]

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "device": self.device,
            "gpu_layers": self.gpu_layers,
            "pid": self.pid,
            "dimension": self.dimension,
            "norm": self.norm,
            "load_seconds": self.load_seconds,
            "embedding_ms": self.embedding_ms,
            "unload_ms": self.unload_ms,
            "working_set_bytes": self.working_set_bytes,
            "nvidia_compute_present": self.nvidia_compute_present,
            "vram_before_mib": self.vram_before_mib,
            "vram_loaded_mib": self.vram_loaded_mib,
            "vram_after_mib": self.vram_after_mib,
            "vram_delta_mib": self.vram_delta_mib,
        }


@dataclass(frozen=True)
class GpuCanaryResult:
    executable_path: str
    discovered_devices: Tuple[str, ...]
    selected_device: str
    text: GpuModelCanaryResult
    code: GpuModelCanaryResult

    def to_dict(self) -> dict[str, object]:
        return {
            "execution_mode": "GPU",
            "executable_path": self.executable_path,
            "discovered_devices": list(self.discovered_devices),
            "selected_device": self.selected_device,
            "text": self.text.to_dict(),
            "code": self.code.to_dict(),
        }


def _is_compute_pid(pid: int) -> Optional[bool]:
    pids = nvidia_compute_pids()
    if pids is None:
        return None
    return pid in pids


def _delta(
    before: Optional[int],
    loaded: Optional[int],
) -> Optional[int]:
    if before is None or loaded is None:
        return None
    return loaded - before


def _text_gpu_config(
    executable_path: Path,
    model_path: Path,
    *,
    device: str,
) -> LlamaServerConfig:
    base = LlamaServerConfig(
        executable_path=Path(executable_path),
        model_path=Path(model_path),
        gpu_layers=99,
    )
    return build_gpu_config(base, device=device)


def _run_text_gpu(
    executable_path: Path,
    model_path: Path,
    *,
    device: str,
) -> GpuModelCanaryResult:
    config = _text_gpu_config(
        executable_path,
        model_path,
        device=device,
    )
    lifecycle = TextModelLifecycle(config)
    before = current_vram_used_mib()
    try:
        started = time.perf_counter()
        loaded = lifecycle.load(timeout_seconds=120)
        load_seconds = time.perf_counter() - started
        if loaded.pid is None:
            raise RuntimeError("text GPU lifecycle reached READY without pid")

        pid = int(loaded.pid)
        loaded_vram = current_vram_used_mib()

        client = TextEmbeddingClient(lifecycle)
        query_started = time.perf_counter()
        vector = client.embed_query(
            "CodeBridge GPU production canary text retrieval"
        )
        embedding_ms = (time.perf_counter() - query_started) * 1000.0

        working_set = windows_process_working_set_bytes(pid)
        compute_present = _is_compute_pid(pid)

        unload_started = time.perf_counter()
        unloaded = lifecycle.unload(timeout_seconds=15)
        unload_ms = (time.perf_counter() - unload_started) * 1000.0
        if unloaded.process_alive:
            raise RuntimeError("text GPU model remained alive after unload")

        after = current_vram_used_mib()
        delta = _delta(before, loaded_vram)
        if delta is not None and delta <= 0:
            raise RuntimeError(
                "text GPU canary did not increase observed VRAM usage"
            )

        return GpuModelCanaryResult(
            model="jina-v5-text-small-retrieval",
            device=device,
            gpu_layers=config.gpu_layers,
            pid=pid,
            dimension=vector.dimension,
            norm=vector.norm,
            load_seconds=load_seconds,
            embedding_ms=embedding_ms,
            unload_ms=unload_ms,
            working_set_bytes=working_set,
            nvidia_compute_present=compute_present,
            vram_before_mib=before,
            vram_loaded_mib=loaded_vram,
            vram_after_mib=after,
            vram_delta_mib=delta,
        )
    finally:
        if lifecycle.snapshot().process_alive:
            lifecycle.unload(timeout_seconds=15)


def _run_code_gpu(
    executable_path: Path,
    model_path: Path,
    *,
    device: str,
) -> GpuModelCanaryResult:
    config = build_gpu_config(
        build_code_server_config(
            executable_path=executable_path,
            model_path=model_path,
            gpu_layers=99,
        ),
        device=device,
    )
    lifecycle = CodeModelLifecycle(config)
    before = current_vram_used_mib()
    try:
        started = time.perf_counter()
        loaded = lifecycle.load(timeout_seconds=180)
        load_seconds = time.perf_counter() - started
        if loaded.pid is None:
            raise RuntimeError("code GPU lifecycle reached READY without pid")

        pid = int(loaded.pid)
        loaded_vram = current_vram_used_mib()

        client = CodeEmbeddingClient(lifecycle)
        query_started = time.perf_counter()
        vector = client.embed_query(
            CodeRetrievalTask.NL2CODE,
            "where is the cancellation flow implemented?",
        )
        embedding_ms = (time.perf_counter() - query_started) * 1000.0

        working_set = windows_process_working_set_bytes(pid)
        compute_present = _is_compute_pid(pid)

        unload_started = time.perf_counter()
        unloaded = lifecycle.unload(timeout_seconds=20)
        unload_ms = (time.perf_counter() - unload_started) * 1000.0
        if unloaded.process_alive:
            raise RuntimeError("code GPU model remained alive after unload")

        after = current_vram_used_mib()
        delta = _delta(before, loaded_vram)
        if delta is not None and delta <= 0:
            raise RuntimeError(
                "code GPU canary did not increase observed VRAM usage"
            )

        return GpuModelCanaryResult(
            model="jina-code-embeddings-1.5b",
            device=device,
            gpu_layers=config.gpu_layers,
            pid=pid,
            dimension=vector.dimension,
            norm=vector.norm,
            load_seconds=load_seconds,
            embedding_ms=embedding_ms,
            unload_ms=unload_ms,
            working_set_bytes=working_set,
            nvidia_compute_present=compute_present,
            vram_before_mib=before,
            vram_loaded_mib=loaded_vram,
            vram_after_mib=after,
            vram_delta_mib=delta,
        )
    finally:
        if lifecycle.snapshot().process_alive:
            lifecycle.unload(timeout_seconds=20)


def run_gpu_canary(
    executable_path: str | Path,
) -> GpuCanaryResult:
    executable = Path(executable_path)
    devices = discover_llama_devices(executable)
    if not devices:
        raise RuntimeError("no compatible llama.cpp GPU device was discovered")

    device = devices[0]
    text = _run_text_gpu(
        executable,
        resolve_selected_model_path(),
        device=device,
    )
    code = _run_code_gpu(
        executable,
        resolve_selected_code_model_path(),
        device=device,
    )

    if text.nvidia_compute_present is False:
        raise RuntimeError(
            "text GPU process was not observed in NVIDIA compute list"
        )
    if code.nvidia_compute_present is False:
        raise RuntimeError(
            "code GPU process was not observed in NVIDIA compute list"
        )

    return GpuCanaryResult(
        executable_path=str(executable),
        discovered_devices=devices,
        selected_device=device,
        text=text,
        code=code,
    )
