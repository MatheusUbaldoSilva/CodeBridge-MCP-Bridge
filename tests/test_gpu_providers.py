import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app_rewrite"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from gpu_providers import (
    GpuProviderManager,
    NvidiaSmiProvider,
    legacy_gpu_snapshot,
)


LUID = "00000000:0000C350"


def nvidia_device(
    *,
    name="NVIDIA GeForce RTX 3050 6GB Laptop GPU",
    luid=LUID,
    primary=True,
):
    return {
        "index": 1,
        "luid": luid,
        "name": name,
        "vendor_id": "10DE",
        "vendor_name": "NVIDIA",
        "adapter_type": "discrete",
        "is_primary": primary,
        "percent": 2.0,
        "vram_used_bytes": 200 * 1024**2,
        "vram_total_bytes": 6000 * 1024**2,
        "vram_percent": 3.3,
        "temperature_c": None,
        "telemetry_source": "windows_pdh",
    }


class NvidiaProviderTests(unittest.TestCase):
    def test_collect_parses_nvidia_metrics(self):
        output = (
            "0, NVIDIA GeForce RTX 3050 6GB "
            "Laptop GPU, 33, 213, 6144, 53\n"
        )

        def runner(*args, **kwargs):
            return SimpleNamespace(
                returncode=0,
                stdout=output,
                stderr="",
            )

        provider = NvidiaSmiProvider(
            runner=runner
        )
        result = provider.collect(
            [nvidia_device()]
        )[LUID]

        self.assertEqual(
            result["percent"],
            33.0,
        )
        self.assertEqual(
            result["vram_used_bytes"],
            213 * 1024**2,
        )
        self.assertEqual(
            result["vram_total_bytes"],
            6144 * 1024**2,
        )
        self.assertAlmostEqual(
            result["vram_percent"],
            213 / 6144 * 100.0,
        )
        self.assertEqual(
            result["temperature_c"],
            53.0,
        )
        self.assertEqual(
            result["provider"],
            "nvidia_smi",
        )

    def test_ambiguous_duplicate_names_are_not_guessed(self):
        devices = [
            nvidia_device(
                luid="00000000:00000001",
                primary=True,
            ),
            nvidia_device(
                luid="00000000:00000002",
                primary=False,
            ),
        ]
        rows = [
            {"index": 0, "name": devices[0]["name"]},
            {"index": 1, "name": devices[1]["name"]},
        ]

        self.assertEqual(
            NvidiaSmiProvider._match_rows(
                devices,
                rows,
            ),
            {},
        )

    def test_non_nvidia_device_is_ignored(self):
        provider = NvidiaSmiProvider(
            runner=lambda *args, **kwargs: (
                self.fail(
                    "runner should not be called"
                )
            )
        )
        result = provider.collect(
            [
                {
                    "luid": "x",
                    "vendor_id": "1002",
                }
            ]
        )
        self.assertEqual(result, {})


class ProviderManagerTests(unittest.TestCase):
    def test_enrichment_overrides_generic_metrics_without_losing_device_identity(self):
        class Provider:
            name = "test_provider"

            @staticmethod
            def supports(device):
                return (
                    device.get("vendor_id")
                    == "10DE"
                )

            @staticmethod
            def collect(devices):
                return {
                    LUID: {
                        "percent": 44.0,
                        "temperature_c": 57.0,
                        "provider": "test_provider",
                    }
                }

        source = {
            "devices": [nvidia_device()],
            "primary": nvidia_device(),
            "source": "windows_pdh",
            "error": None,
        }
        enriched = GpuProviderManager(
            providers=[Provider()]
        ).enrich(source)
        primary = enriched["primary"]

        self.assertEqual(
            primary["name"],
            source["primary"]["name"],
        )
        self.assertEqual(
            primary["percent"],
            44.0,
        )
        self.assertEqual(
            primary["temperature_c"],
            57.0,
        )
        self.assertEqual(
            primary["telemetry_source"],
            "test_provider",
        )
        self.assertEqual(
            primary["metric_sources"][
                "temperature_c"
            ],
            "test_provider",
        )
        self.assertEqual(
            source["devices"][0]["percent"],
            2.0,
        )

    def test_provider_failure_preserves_generic_metrics(self):
        class Provider:
            name = "broken"

            @staticmethod
            def supports(device):
                return True

            @staticmethod
            def collect(devices):
                raise RuntimeError("boom")

        source = {
            "devices": [nvidia_device()],
            "primary": nvidia_device(),
            "source": "windows_pdh",
            "error": None,
        }
        enriched = GpuProviderManager(
            providers=[Provider()]
        ).enrich(source)

        self.assertEqual(
            enriched["primary"]["percent"],
            2.0,
        )
        self.assertIsNone(
            enriched["primary"][
                "temperature_c"
            ]
        )
        self.assertEqual(
            enriched["provider_errors"][0][
                "provider"
            ],
            "broken",
        )

    def test_legacy_snapshot_requires_real_temperature_provider(self):
        generic = {
            "primary": nvidia_device(),
        }
        self.assertIsNone(
            legacy_gpu_snapshot(generic)
        )

        enriched_device = nvidia_device()
        enriched_device.update(
            {
                "percent": 33.0,
                "vram_used_bytes": (
                    213 * 1024**2
                ),
                "vram_total_bytes": (
                    6144 * 1024**2
                ),
                "temperature_c": 53.0,
                "metric_sources": {
                    "temperature_c": (
                        "nvidia_smi"
                    ),
                },
            }
        )
        legacy = legacy_gpu_snapshot(
            {
                "primary": enriched_device,
            }
        )
        self.assertEqual(
            legacy["temp_c"],
            53.0,
        )
        self.assertEqual(
            legacy["used_mb"],
            213.0,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
