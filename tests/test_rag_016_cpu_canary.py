import unittest
from pathlib import Path
from unittest import mock

from rag.benchmark.cpu_canary import (
    CpuModelCanaryResult,
    CpuOnlyCanaryResult,
    _text_cpu_config,
    nvidia_compute_pids,
)


class Rag016CpuCanaryTests(unittest.TestCase):
    def test_text_cpu_config_disables_gpu_offload(self):
        config = _text_cpu_config(
            Path("llama-server.exe"),
            Path("model.gguf"),
        )

        self.assertEqual(config.device, "none")
        self.assertEqual(config.gpu_layers, 0)

    def test_nvidia_pid_probe_is_optional_when_binary_missing(self):
        with mock.patch(
            "rag.benchmark.cpu_canary.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            self.assertIsNone(nvidia_compute_pids())

    def test_nvidia_pid_probe_parses_unique_numeric_pids(self):
        completed = mock.Mock(
            returncode=0,
            stdout="123\n456\n123\nN/A\n",
        )
        with mock.patch(
            "rag.benchmark.cpu_canary.subprocess.run",
            return_value=completed,
        ):
            self.assertEqual(
                nvidia_compute_pids(),
                (123, 456),
            )

    def test_result_contract_freezes_cpu_only_mode(self):
        item = CpuModelCanaryResult(
            model="model",
            pid=123,
            dimension=1024,
            norm=1.0,
            load_seconds=1.0,
            embedding_ms=10.0,
            unload_ms=20.0,
            working_set_bytes=100,
            nvidia_compute_present=False,
        )
        result = CpuOnlyCanaryResult(
            executable_path="llama-server.exe",
            device="none",
            gpu_layers=0,
            text=item,
            code=item,
        )

        payload = result.to_dict()

        self.assertEqual(payload["execution_mode"], "CPU_ONLY")
        self.assertEqual(payload["device"], "none")
        self.assertEqual(payload["gpu_layers"], 0)


if __name__ == "__main__":
    unittest.main()
