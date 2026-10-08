"""Benchmark metrics and resource probes for RAG-014-C."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import time
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class RetrievalMetrics:
    query_count: int
    recall_at_5: float
    recall_at_10: float
    mrr: float

    def to_dict(self) -> dict[str, object]:
        return {
            "query_count": self.query_count,
            "recall_at_5": self.recall_at_5,
            "recall_at_10": self.recall_at_10,
            "mrr": self.mrr,
        }


@dataclass(frozen=True)
class ResourceSnapshot:
    ram_rss_bytes: int
    vram_used_mib: int | None
    index_size_bytes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "ram_rss_bytes": self.ram_rss_bytes,
            "vram_used_mib": self.vram_used_mib,
            "index_size_bytes": self.index_size_bytes,
        }


def evaluate_ranked_paths(
    ranked_paths_by_query: Mapping[str, Sequence[str]],
    expected_paths_by_query: Mapping[str, Sequence[str]],
) -> RetrievalMetrics:
    if set(ranked_paths_by_query) != set(expected_paths_by_query):
        raise ValueError("ranked and expected query ids must match exactly")

    query_ids = tuple(sorted(expected_paths_by_query))
    if not query_ids:
        raise ValueError("at least one benchmark query is required")

    hit5 = 0
    hit10 = 0
    reciprocal_rank_sum = 0.0

    for query_id in query_ids:
        ranked = tuple(ranked_paths_by_query[query_id])
        expected = set(expected_paths_by_query[query_id])
        if not expected:
            raise ValueError(f"{query_id} must have expected paths")

        first_rank = None
        for index, path in enumerate(ranked, 1):
            if path in expected:
                first_rank = index
                break

        if first_rank is not None:
            reciprocal_rank_sum += 1.0 / first_rank
            hit5 += int(first_rank <= 5)
            hit10 += int(first_rank <= 10)

    count = len(query_ids)
    return RetrievalMetrics(
        query_count=count,
        recall_at_5=hit5 / count,
        recall_at_10=hit10 / count,
        mrr=reciprocal_rank_sum / count,
    )


def directory_size_bytes(path: str | Path) -> int:
    root = Path(path)
    if not root.exists():
        return 0
    if root.is_file():
        return root.stat().st_size
    total = 0
    for item in root.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def process_rss_bytes(pid: int) -> int:
    """Return process RSS without adding a benchmark dependency."""

    if not isinstance(pid, int) or pid < 1:
        raise ValueError("pid must be an integer >= 1")

    if __import__("os").name == "nt":
        import ctypes
        from ctypes import wintypes

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

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        PROCESS_VM_READ = 0x0010
        access = PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ
        open_process = ctypes.windll.kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        handle = open_process(access, False, pid)
        if not handle:
            raise RuntimeError(f"OpenProcess failed for pid {pid}")
        try:
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            get_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
            get_memory_info.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            get_memory_info.restype = wintypes.BOOL
            ok = get_memory_info(
                handle,
                ctypes.byref(counters),
                counters.cb,
            )
            if not ok:
                raise RuntimeError("GetProcessMemoryInfo failed")
            return int(counters.WorkingSetSize)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    if pid != __import__("os").getpid():
        raise RuntimeError("cross-process RSS probe is only implemented on Windows")
    import resource

    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value * 1024


def current_process_rss_bytes() -> int:
    return process_rss_bytes(__import__("os").getpid())


def current_vram_used_mib() -> int | None:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0:
        return None

    values = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            values.append(int(line))
        except ValueError:
            return None
    return sum(values) if values else None


def capture_resource_snapshot(index_paths: Iterable[str | Path]) -> ResourceSnapshot:
    return ResourceSnapshot(
        ram_rss_bytes=current_process_rss_bytes(),
        vram_used_mib=current_vram_used_mib(),
        index_size_bytes=sum(directory_size_bytes(path) for path in index_paths),
    )


def measure_latency_ms(callable_, *, repeat: int = 1) -> tuple[float, ...]:
    if not callable(callable_):
        raise ValueError("callable_ must be callable")
    if not isinstance(repeat, int) or repeat < 1:
        raise ValueError("repeat must be >= 1")

    samples = []
    for _ in range(repeat):
        started = time.perf_counter()
        callable_()
        samples.append((time.perf_counter() - started) * 1000.0)
    return tuple(samples)
