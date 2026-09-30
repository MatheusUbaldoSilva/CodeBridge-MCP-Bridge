import ctypes
import os
import re
from ctypes import wintypes


PDH_FMT_DOUBLE = 0x00000200
PDH_MORE_DATA = 0x800007D2
PDH_CSTATUS_VALID_DATA = 0x00000000
PDH_CSTATUS_NEW_DATA = 0x00000001

_GPU_ENGINE_COUNTER = (
    r"\GPU Engine(*)\Utilization Percentage"
)
_GPU_DEDICATED_COUNTER = (
    r"\GPU Adapter Memory(*)\Dedicated Usage"
)
_GPU_SHARED_COUNTER = (
    r"\GPU Adapter Memory(*)\Shared Usage"
)

_LUID_RE = re.compile(
    r"luid_0x([0-9a-f]+)_0x([0-9a-f]+)",
    re.IGNORECASE,
)
_ENGINE_RE = re.compile(
    r"_eng_([0-9]+)_",
    re.IGNORECASE,
)


class _ValueUnion(ctypes.Union):
    _fields_ = [
        ("long_value", wintypes.LONG),
        ("double_value", ctypes.c_double),
        ("large_value", ctypes.c_longlong),
        ("ansi_string_value", ctypes.c_char_p),
        ("wide_string_value", ctypes.c_wchar_p),
    ]


class _FormattedCounterValue(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [
        ("status", wintypes.DWORD),
        ("value", _ValueUnion),
    ]


class _FormattedCounterValueItem(ctypes.Structure):
    _fields_ = [
        ("name", wintypes.LPWSTR),
        ("value", _FormattedCounterValue),
    ]


def _status_code(value):
    return ctypes.c_uint32(value).value


def _normalize_luid(value):
    text = str(value or "").strip().upper()
    if ":" not in text:
        return ""
    high, low = text.split(":", 1)
    try:
        return (
            f"{int(high, 16) & 0xFFFFFFFF:08X}:"
            f"{int(low, 16) & 0xFFFFFFFF:08X}"
        )
    except ValueError:
        return ""


def _luid_from_instance(name):
    match = _LUID_RE.search(str(name or ""))
    if match is None:
        return ""
    return (
        f"{int(match.group(1), 16) & 0xFFFFFFFF:08X}:"
        f"{int(match.group(2), 16) & 0xFFFFFFFF:08X}"
    )


def _engine_from_instance(name):
    match = _ENGINE_RE.search(str(name or ""))
    if match is None:
        return None
    return int(match.group(1))


def _aggregate_engine_usage(samples):
    per_engine = {}
    for sample in samples or []:
        luid = _luid_from_instance(
            sample.get("name")
        )
        engine = _engine_from_instance(
            sample.get("name")
        )
        if not luid or engine is None:
            continue
        value = max(
            0.0,
            float(sample.get("value") or 0.0),
        )
        key = (luid, engine)
        per_engine[key] = min(
            100.0,
            per_engine.get(key, 0.0) + value,
        )

    per_gpu = {}
    for (luid, _engine), value in per_engine.items():
        per_gpu[luid] = max(
            per_gpu.get(luid, 0.0),
            value,
        )
    return per_gpu


def _aggregate_memory_usage(samples):
    result = {}
    for sample in samples or []:
        luid = _luid_from_instance(
            sample.get("name")
        )
        if not luid:
            continue
        result[luid] = (
            result.get(luid, 0.0)
            + max(
                0.0,
                float(sample.get("value") or 0.0),
            )
        )
    return result


def build_gpu_metrics(
    devices,
    engine_samples,
    dedicated_samples,
    shared_samples,
):
    engine_usage = _aggregate_engine_usage(
        engine_samples
    )
    dedicated_usage = _aggregate_memory_usage(
        dedicated_samples
    )
    shared_usage = _aggregate_memory_usage(
        shared_samples
    )

    metrics = []
    for device in devices or []:
        luid = _normalize_luid(
            device.get("luid")
        )
        dedicated_total = int(
            device.get("dedicated_vram_bytes")
            or 0
        )
        dedicated_used = int(
            dedicated_usage.get(luid, 0.0)
        )
        shared_used = int(
            shared_usage.get(luid, 0.0)
        )

        vram_percent = None
        if dedicated_total > 0:
            vram_percent = max(
                0.0,
                min(
                    100.0,
                    (
                        dedicated_used
                        / dedicated_total
                        * 100.0
                    ),
                ),
            )

        metric = {
            "index": device.get("index"),
            "luid": luid,
            "name": device.get("name"),
            "vendor_id": device.get(
                "vendor_id"
            ),
            "vendor_name": device.get(
                "vendor_name"
            ),
            "adapter_type": device.get(
                "adapter_type"
            ),
            "is_primary": bool(
                device.get("is_primary")
            ),
            "percent": max(
                0.0,
                min(
                    100.0,
                    engine_usage.get(
                        luid,
                        0.0,
                    ),
                ),
            ),
            "vram_used_bytes": dedicated_used,
            "vram_total_bytes": dedicated_total,
            "vram_percent": vram_percent,
            "shared_used_bytes": shared_used,
            "shared_total_bytes": int(
                device.get(
                    "shared_system_bytes"
                )
                or 0
            ),
            "temperature_c": None,
            "telemetry_source": "windows_pdh",
        }
        metrics.append(metric)

    primary = next(
        (
            metric
            for metric in metrics
            if metric["is_primary"]
        ),
        None,
    )
    return {
        "devices": metrics,
        "primary": primary,
        "source": "windows_pdh",
    }


class _PdhGpuQuery:
    def __init__(self):
        if os.name != "nt":
            raise OSError(
                "PDH GPU telemetry requires Windows"
            )

        self._pdh = ctypes.WinDLL("pdh")
        self._query = ctypes.c_void_p()
        self._counters = {}
        self._bind()

        result = self._open_query(
            None,
            None,
            ctypes.byref(self._query),
        )
        self._check(result, "PdhOpenQueryW")

        try:
            self._add_counter(
                "engine",
                _GPU_ENGINE_COUNTER,
            )
            self._add_counter(
                "dedicated",
                _GPU_DEDICATED_COUNTER,
            )
            self._add_counter(
                "shared",
                _GPU_SHARED_COUNTER,
            )
            self.collect()
        except Exception:
            self.close()
            raise

    def _bind(self):
        self._open_query = (
            self._pdh.PdhOpenQueryW
        )
        self._open_query.argtypes = [
            wintypes.LPCWSTR,
            ctypes.c_void_p,
            ctypes.POINTER(
                ctypes.c_void_p
            ),
        ]
        self._open_query.restype = wintypes.LONG

        self._add_english_counter = (
            self._pdh.PdhAddEnglishCounterW
        )
        self._add_english_counter.argtypes = [
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            ctypes.c_void_p,
            ctypes.POINTER(
                ctypes.c_void_p
            ),
        ]
        self._add_english_counter.restype = (
            wintypes.LONG
        )

        self._collect = (
            self._pdh.PdhCollectQueryData
        )
        self._collect.argtypes = [
            ctypes.c_void_p
        ]
        self._collect.restype = wintypes.LONG

        self._get_array = (
            self._pdh
            .PdhGetFormattedCounterArrayW
        )
        self._get_array.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        self._get_array.restype = wintypes.LONG

        self._close_query = (
            self._pdh.PdhCloseQuery
        )
        self._close_query.argtypes = [
            ctypes.c_void_p
        ]
        self._close_query.restype = wintypes.LONG

    @staticmethod
    def _check(result, action):
        code = _status_code(result)
        if code != 0:
            raise OSError(
                f"{action} failed: 0x{code:08X}"
            )

    def _add_counter(self, key, path):
        counter = ctypes.c_void_p()
        result = self._add_english_counter(
            self._query,
            path,
            None,
            ctypes.byref(counter),
        )
        self._check(
            result,
            f"PdhAddEnglishCounterW({key})",
        )
        self._counters[key] = counter

    def collect(self):
        if not self._query.value:
            return False
        result = self._collect(self._query)
        self._check(
            result,
            "PdhCollectQueryData",
        )
        return True

    def _read_counter(self, key):
        counter = self._counters[key]
        size = wintypes.DWORD(0)
        count = wintypes.DWORD(0)

        result = self._get_array(
            counter,
            PDH_FMT_DOUBLE,
            ctypes.byref(size),
            ctypes.byref(count),
            None,
        )
        code = _status_code(result)
        if code not in (
            PDH_MORE_DATA,
            PDH_CSTATUS_VALID_DATA,
        ):
            raise OSError(
                "PdhGetFormattedCounterArrayW "
                f"size failed: 0x{code:08X}"
            )
        if size.value == 0:
            return []

        buffer = ctypes.create_string_buffer(
            size.value
        )
        result = self._get_array(
            counter,
            PDH_FMT_DOUBLE,
            ctypes.byref(size),
            ctypes.byref(count),
            buffer,
        )
        self._check(
            result,
            "PdhGetFormattedCounterArrayW",
        )

        items = ctypes.cast(
            buffer,
            ctypes.POINTER(
                _FormattedCounterValueItem
            ),
        )
        values = []
        for index in range(count.value):
            item = items[index]
            if item.value.status not in (
                PDH_CSTATUS_VALID_DATA,
                PDH_CSTATUS_NEW_DATA,
            ):
                continue
            values.append(
                {
                    "name": item.name or "",
                    "value": (
                        item.value.double_value
                    ),
                }
            )
        return values

    def snapshot(self):
        self.collect()
        return {
            "engine": self._read_counter(
                "engine"
            ),
            "dedicated": self._read_counter(
                "dedicated"
            ),
            "shared": self._read_counter(
                "shared"
            ),
        }

    def close(self):
        query = self._query
        self._query = ctypes.c_void_p()
        self._counters.clear()
        if query.value:
            self._close_query(query)


class WindowsGpuTelemetry:
    def __init__(self, devices):
        self.devices = list(devices or [])
        self._query = None
        self.error = None
        if os.name == "nt" and self.devices:
            try:
                self._query = _PdhGpuQuery()
            except Exception as exc:
                self.error = (
                    f"{type(exc).__name__}: {exc}"
                )

    def snapshot(self):
        if self._query is None:
            return {
                "devices": [],
                "primary": None,
                "source": "windows_pdh",
                "error": self.error,
            }

        try:
            samples = self._query.snapshot()
            result = build_gpu_metrics(
                self.devices,
                samples["engine"],
                samples["dedicated"],
                samples["shared"],
            )
            result["error"] = None
            self.error = None
            return result
        except Exception as exc:
            self.error = (
                f"{type(exc).__name__}: {exc}"
            )
            return {
                "devices": [],
                "primary": None,
                "source": "windows_pdh",
                "error": self.error,
            }

    def close(self):
        if self._query is not None:
            try:
                self._query.close()
            finally:
                self._query = None
