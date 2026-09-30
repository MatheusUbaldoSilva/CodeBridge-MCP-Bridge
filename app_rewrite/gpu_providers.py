import copy
import subprocess


def _number(value):
    text = str(value or "").strip()
    if not text or text.upper() in {
        "N/A",
        "[N/A]",
        "NA",
        "NOT SUPPORTED",
    }:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _normalize_name(value):
    return " ".join(
        str(value or "").split()
    ).casefold()


class NvidiaSmiProvider:
    name = "nvidia_smi"
    vendor_id = "10DE"

    def __init__(self, runner=None):
        self._runner = (
            runner or subprocess.run
        )

    def supports(self, device):
        return (
            str(
                device.get("vendor_id") or ""
            ).upper()
            == self.vendor_id
        )

    def _query(self):
        command = [
            "nvidia-smi",
            (
                "--query-gpu="
                "index,name,utilization.gpu,"
                "memory.used,memory.total,"
                "temperature.gpu"
            ),
            "--format=csv,noheader,nounits",
        ]
        result = self._runner(
            command,
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0,
            ),
        )
        if (
            result.returncode != 0
            or not result.stdout.strip()
        ):
            message = (
                result.stderr.strip()
                or "nvidia-smi returned no data"
            )
            raise RuntimeError(message)

        rows = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = [
                part.strip()
                for part in line.split(",")
            ]
            if len(parts) != 6:
                continue
            try:
                index = int(parts[0])
            except ValueError:
                continue
            rows.append(
                {
                    "index": index,
                    "name": parts[1],
                    "percent": _number(
                        parts[2]
                    ),
                    "used_mb": _number(
                        parts[3]
                    ),
                    "total_mb": _number(
                        parts[4]
                    ),
                    "temperature_c": _number(
                        parts[5]
                    ),
                }
            )
        if not rows:
            raise RuntimeError(
                "nvidia-smi returned no parseable GPU rows"
            )
        return rows

    @staticmethod
    def _match_rows(devices, rows):
        devices = list(devices or [])
        rows = list(rows or [])
        matches = {}

        if len(devices) == 1 and len(rows) == 1:
            matches[devices[0]["luid"]] = rows[0]
            return matches

        device_groups = {}
        row_groups = {}
        for device in devices:
            device_groups.setdefault(
                _normalize_name(
                    device.get("name")
                ),
                [],
            ).append(device)
        for row in rows:
            row_groups.setdefault(
                _normalize_name(
                    row.get("name")
                ),
                [],
            ).append(row)

        for name, group in device_groups.items():
            matched_rows = row_groups.get(
                name,
                [],
            )
            if (
                len(group) == 1
                and len(matched_rows) == 1
            ):
                matches[group[0]["luid"]] = (
                    matched_rows[0]
                )
        return matches

    def collect(self, devices):
        supported = [
            device
            for device in (devices or [])
            if self.supports(device)
        ]
        if not supported:
            return {}

        rows = self._query()
        matches = self._match_rows(
            supported,
            rows,
        )
        result = {}
        for device in supported:
            row = matches.get(
                device.get("luid")
            )
            if row is None:
                continue

            patch = {}
            if row["percent"] is not None:
                patch["percent"] = max(
                    0.0,
                    min(
                        100.0,
                        row["percent"],
                    ),
                )
            if row["used_mb"] is not None:
                patch["vram_used_bytes"] = int(
                    row["used_mb"] * 1024**2
                )
            if row["total_mb"] is not None:
                patch["vram_total_bytes"] = int(
                    row["total_mb"] * 1024**2
                )
            if (
                row["used_mb"] is not None
                and row["total_mb"] is not None
                and row["total_mb"] > 0
            ):
                patch["vram_percent"] = max(
                    0.0,
                    min(
                        100.0,
                        (
                            row["used_mb"]
                            / row["total_mb"]
                            * 100.0
                        ),
                    ),
                )
            if (
                row["temperature_c"]
                is not None
            ):
                patch["temperature_c"] = (
                    row["temperature_c"]
                )

            if patch:
                patch["provider"] = self.name
                result[device["luid"]] = patch

        return result


class GpuProviderManager:
    def __init__(self, providers=None):
        self.providers = list(
            providers
            if providers is not None
            else [NvidiaSmiProvider()]
        )

    def enrich(self, snapshot):
        result = copy.deepcopy(
            snapshot
            or {
                "devices": [],
                "primary": None,
                "source": "windows_pdh",
            }
        )
        devices = result.get("devices") or []
        errors = []

        for provider in self.providers:
            if not any(
                provider.supports(device)
                for device in devices
            ):
                continue
            try:
                patches = provider.collect(
                    devices
                )
            except Exception as exc:
                errors.append(
                    {
                        "provider": provider.name,
                        "error": (
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                    }
                )
                continue

            for device in devices:
                patch = patches.get(
                    device.get("luid")
                )
                if not patch:
                    continue

                provider_name = patch.pop(
                    "provider",
                    provider.name,
                )
                metric_sources = dict(
                    device.get(
                        "metric_sources"
                    )
                    or {}
                )
                for key, value in patch.items():
                    device[key] = value
                    if key in {
                        "percent",
                        "vram_used_bytes",
                        "vram_total_bytes",
                        "vram_percent",
                        "temperature_c",
                    }:
                        metric_sources[key] = (
                            provider_name
                        )
                device["metric_sources"] = (
                    metric_sources
                )
                device["telemetry_source"] = (
                    provider_name
                )

        primary = next(
            (
                device
                for device in devices
                if device.get("is_primary")
            ),
            None,
        )
        result["devices"] = devices
        result["primary"] = primary
        result["provider_errors"] = errors
        return result


def legacy_gpu_snapshot(snapshot):
    primary = (
        (snapshot or {}).get("primary")
        or None
    )
    if not primary:
        return None

    sources = (
        primary.get("metric_sources")
        or {}
    )
    if sources.get("temperature_c") != (
        "nvidia_smi"
    ):
        return None

    return {
        "name": primary.get(
            "name",
            "GPU",
        ),
        "percent": float(
            primary.get("percent") or 0.0
        ),
        "used_mb": (
            float(
                primary.get(
                    "vram_used_bytes"
                )
                or 0
            )
            / 1024**2
        ),
        "total_mb": (
            float(
                primary.get(
                    "vram_total_bytes"
                )
                or 0
            )
            / 1024**2
        ),
        "temp_c": float(
            primary.get("temperature_c")
        ),
    }
