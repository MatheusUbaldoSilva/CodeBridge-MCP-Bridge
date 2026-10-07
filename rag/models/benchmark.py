"""Measured runtime cost for Jina v5 text embeddings — RAG-006-G."""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import statistics
import subprocess
import time
from typing import Callable, Iterable, Optional, Sequence, Tuple

from .embedding import TextEmbeddingClient
from .fallback import ModelExecutionMode, TextModelFallbackManager


@dataclass(frozen=True)
class TextRuntimeBenchmark:
    execution_mode: ModelExecutionMode
    cold_start_seconds: float
    warm_query_mean_ms: float
    embeddings_per_second: float
    ram_working_set_bytes: int
    vram_delta_mib: Optional[int]
    unload_ms: float
    warm_query_samples: int
    throughput_samples: int

    def __post_init__(self) -> None:
        if self.cold_start_seconds < 0:
            raise ValueError("cold_start_seconds must be >= 0")
        if self.warm_query_mean_ms < 0:
            raise ValueError("warm_query_mean_ms must be >= 0")
        if self.embeddings_per_second <= 0:
            raise ValueError("embeddings_per_second must be > 0")
        if self.ram_working_set_bytes < 0:
            raise ValueError("ram_working_set_bytes must be >= 0")
        if self.vram_delta_mib is not None and self.vram_delta_mib < 0:
            raise ValueError("vram_delta_mib must be >= 0")
        if self.unload_ms < 0:
            raise ValueError("unload_ms must be >= 0")
        if self.warm_query_samples < 1 or self.throughput_samples < 1:
            raise ValueError("sample counts must be >= 1")


def windows_process_working_set_bytes(pid: int) -> int:
    if pid < 1:
        raise ValueError("pid must be >= 1")
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("Windows process memory probe requires Windows")

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    handle = kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
        False,
        pid,
    )
    if not handle:
        raise RuntimeError("OpenProcess failed for benchmark PID")

    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        ok = psapi.GetProcessMemoryInfo(
            handle,
            ctypes.byref(counters),
            counters.cb,
        )
        if not ok:
            raise RuntimeError("GetProcessMemoryInfo failed")
        return int(counters.WorkingSetSize)
    finally:
        kernel32.CloseHandle(handle)


def nvidia_total_memory_used_mib(
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Optional[int]:
    try:
        completed = runner(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
    except Exception:
        return None

    if int(completed.returncode) != 0:
        return None

    values = []
    for line in (completed.stdout or "").splitlines():
        value = line.strip()
        if not value:
            continue
        try:
            values.append(int(value))
        except ValueError:
            return None

    if not values:
        return None
    return sum(values)


def benchmark_text_runtime(
    manager: TextModelFallbackManager,
    *,
    query_text: str,
    document_texts: Sequence[str],
    warm_query_samples: int = 5,
    ram_probe: Callable[[int], int] = windows_process_working_set_bytes,
    vram_probe: Callable[[], Optional[int]] = nvidia_total_memory_used_mib,
    clock: Callable[[], float] = time.perf_counter,
    client_factory: Callable[..., TextEmbeddingClient] = TextEmbeddingClient,
) -> TextRuntimeBenchmark:
    if not isinstance(manager, TextModelFallbackManager):
        raise ValueError("manager must be TextModelFallbackManager")
    if not isinstance(query_text, str) or not query_text.strip():
        raise ValueError("query_text must be non-empty")
    if warm_query_samples < 1:
        raise ValueError("warm_query_samples must be >= 1")
    documents = tuple(document_texts)
    if not documents or any(
        not isinstance(text, str) or not text.strip()
        for text in documents
    ):
        raise ValueError("document_texts must contain non-empty strings")

    before_vram = vram_probe()

    start = clock()
    runtime = manager.load(timeout_seconds=120)
    cold_start = clock() - start

    if runtime.pid is None:
        manager.unload()
        raise RuntimeError("benchmark runtime has no PID")

    ram_bytes = int(ram_probe(runtime.pid))
    after_vram = vram_probe()
    if before_vram is None or after_vram is None:
        vram_delta = None
    else:
        vram_delta = max(0, int(after_vram) - int(before_vram))

    client = client_factory(manager.active_lifecycle)
    client.embed_query(query_text)

    warm_durations = []
    for _ in range(warm_query_samples):
        started = clock()
        client.embed_query(query_text)
        warm_durations.append(clock() - started)

    throughput_start = clock()
    for text in documents:
        client.embed_document(text)
    throughput_elapsed = clock() - throughput_start
    if throughput_elapsed <= 0:
        manager.unload()
        raise RuntimeError("benchmark clock produced non-positive elapsed time")

    unload_start = clock()
    manager.unload(timeout_seconds=15)
    unload_elapsed = clock() - unload_start

    return TextRuntimeBenchmark(
        execution_mode=runtime.execution_mode,
        cold_start_seconds=cold_start,
        warm_query_mean_ms=statistics.fmean(warm_durations) * 1000.0,
        embeddings_per_second=len(documents) / throughput_elapsed,
        ram_working_set_bytes=ram_bytes,
        vram_delta_mib=vram_delta,
        unload_ms=unload_elapsed * 1000.0,
        warm_query_samples=warm_query_samples,
        throughput_samples=len(documents),
    )
