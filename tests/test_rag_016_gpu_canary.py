import unittest
from pathlib import Path
from unittest import mock

from rag.benchmark.gpu_canary import (
    GpuCanaryResult,
    GpuModelCanaryResult,
    _delta,
    _text_gpu_config,
)


class Rag016GpuCanaryTests(unittest.TestCase):
    def test_text_gpu_config_selects_explicit_device_and_offload(self):
        config = _text_gpu_config(
            Path("llama-server.exe"),
            Path("model.gguf"),
            device="CUDA0",
        )

        self.assertEqual(config.device, "CUDA0")
        self.assertGreaterEqual(config.gpu_layers, 1)

    def test_vram_delta_is_optional(self):
        self.assertIsNone(_delta(None, 100))
        self.assertIsNone(_delta(100, None))
        self.assertEqual(_delta(100, 250), 150)

    def test_result_contract_freezes_gpu_mode(self):
        item = GpuModelCanaryResult(
            model="model",
            device="CUDA0",
            gpu_layers=99,
            pid=123,
            dimension=1024,
            norm=1.0,
            load_seconds=1.0,
            embedding_ms=10.0,
            unload_ms=20.0,
            working_set_bytes=100,
            nvidia_compute_present=True,
            vram_before_mib=100,
            vram_loaded_mib=500,
            vram_after_mib=100,
            vram_delta_mib=400,
        )
        result = GpuCanaryResult(
            executable_path="llama-server.exe",
            discovered_devices=("CUDA0",),
            selected_device="CUDA0",
            text=item,
            code=item,
        )

        payload = result.to_dict()

        self.assertEqual(payload["execution_mode"], "GPU")
        self.assertEqual(payload["selected_device"], "CUDA0")
        self.assertEqual(payload["discovered_devices"], ["CUDA0"])

    def test_no_device_is_rejected_before_model_load(self):
        with mock.patch(
            "rag.benchmark.gpu_canary.discover_llama_devices",
            return_value=(),
        ):
            from rag.benchmark.gpu_canary import run_gpu_canary

            with self.assertRaisesRegex(
                RuntimeError,
                "no compatible llama.cpp GPU device",
            ):
                run_gpu_canary(Path("llama-server.exe"))


if __name__ == "__main__":
    unittest.main()
