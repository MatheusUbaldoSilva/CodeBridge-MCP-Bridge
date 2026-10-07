import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.models.fallback import (
    ModelExecutionMode,
    ModelFallbackError,
    ModelFallbackExhaustedError,
    TextModelFallbackManager,
    build_cpu_fallback_config,
    build_gpu_config,
    discover_llama_devices,
)
from rag.models.lifecycle import (
    LlamaServerConfig,
    ModelLifecycleSnapshot,
    ModelLifecycleState,
    ModelLoadError,
    build_llama_server_argv,
)


class FakeCompleted:
    def __init__(
        self,
        *,
        returncode=0,
        stdout="",
        stderr="",
    ):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeLifecycle:
    def __init__(
        self,
        config,
        *,
        should_fail=False,
        pid=100,
    ):
        self.config = config
        self.should_fail = should_fail
        self.pid = pid
        self.state = ModelLifecycleState.UNLOADED
        self.load_calls = 0
        self.unload_calls = 0

    def snapshot(self):
        return ModelLifecycleSnapshot(
            state=self.state,
            pid=(
                self.pid
                if self.state
                is not ModelLifecycleState.UNLOADED
                else None
            ),
            host=self.config.host,
            port=19111,
            health_url=(
                "http://127.0.0.1:19111/health"
                if self.state
                is not ModelLifecycleState.UNLOADED
                else None
            ),
            executable_path=self.config.executable_path,
            model_path=self.config.model_path,
            process_alive=(
                self.state
                is not ModelLifecycleState.UNLOADED
            ),
        )

    def load(self, **kwargs):
        self.load_calls += 1
        if self.should_fail:
            self.state = ModelLifecycleState.UNLOADED
            raise ModelLoadError(
                "simulated load failure"
            )
        self.state = ModelLifecycleState.READY
        return self.snapshot()

    def mark_idle(self):
        self.state = ModelLifecycleState.IDLE
        return self.snapshot()

    def mark_ready(self):
        self.state = ModelLifecycleState.READY
        return self.snapshot()

    def unload(self, **kwargs):
        self.unload_calls += 1
        self.state = ModelLifecycleState.UNLOADED
        return self.snapshot()


class RagTextCpuFallbackTests(unittest.TestCase):
    def config(
        self,
        root: Path,
        *,
        device=None,
        gpu_layers=99,
    ):
        executable = root / "llama-server.exe"
        model = root / "model.gguf"
        executable.write_bytes(b"x")
        model.write_bytes(b"x")
        return LlamaServerConfig(
            executable_path=executable,
            model_path=model,
            port=0,
            gpu_layers=gpu_layers,
            device=device,
            log_path=root / "server.log",
        )

    def test_cpu_config_forces_device_none_and_zero_layers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = self.config(
                Path(temp_dir)
            )
            cpu = build_cpu_fallback_config(
                base
            )

        self.assertEqual(cpu.device, "none")
        self.assertEqual(cpu.gpu_layers, 0)

    def test_device_none_rejects_nonzero_gpu_layers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                self.config(
                    Path(temp_dir),
                    device="none",
                    gpu_layers=1,
                )

    def test_gpu_config_requires_explicit_device(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = self.config(Path(temp_dir))
            gpu = build_gpu_config(
                base,
                device="CUDA0",
            )

        self.assertEqual(gpu.device, "CUDA0")
        self.assertGreaterEqual(
            gpu.gpu_layers,
            1,
        )

    def test_argv_contains_explicit_cpu_device(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cpu = build_cpu_fallback_config(
                self.config(Path(temp_dir))
            )
            argv = build_llama_server_argv(
                cpu,
                resolved_port=19111,
            )

        self.assertIn("--device", argv)
        self.assertIn("none", argv)
        self.assertIn("-ngl", argv)
        self.assertEqual(
            argv[argv.index("-ngl") + 1],
            "0",
        )

    def test_device_discovery_parses_llama_cpp_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            executable = root / "llama-server.exe"
            executable.write_bytes(b"x")
            calls = []

            def runner(argv, **kwargs):
                calls.append((argv, kwargs))
                return FakeCompleted(
                    stdout=(
                        "Available devices:\n"
                        "  CUDA0: NVIDIA GPU (6143 MiB)\n"
                        "  VULKAN0: Other GPU (2048 MiB)\n"
                    )
                )

            devices = discover_llama_devices(
                executable,
                runner=runner,
            )

        self.assertEqual(
            devices,
            ("CUDA0", "VULKAN0"),
        )
        self.assertEqual(
            calls[0][0],
            [
                str(executable),
                "--list-devices",
            ],
        )
        self.assertFalse(
            calls[0][1]["shell"]
        )

    def test_auto_without_gpu_goes_directly_to_cpu(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = self.config(Path(temp_dir))
            created = []

            def factory(config):
                lifecycle = FakeLifecycle(
                    config,
                    pid=200,
                )
                created.append(lifecycle)
                return lifecycle

            manager = TextModelFallbackManager.auto(
                base,
                lifecycle_factory=factory,
                device_discovery=lambda path: (),
            )
            snapshot = manager.load()

        self.assertEqual(
            snapshot.execution_mode,
            ModelExecutionMode.CPU,
        )
        self.assertTrue(snapshot.fallback_used)
        self.assertIn(
            "no llama.cpp GPU device discovered",
            snapshot.gpu_error,
        )
        self.assertEqual(len(created), 1)
        self.assertEqual(
            created[0].config.device,
            "none",
        )

    def test_gpu_success_does_not_start_cpu(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base = self.config(root)
            gpu = build_gpu_config(
                base,
                device="CUDA0",
            )
            cpu = build_cpu_fallback_config(
                base
            )
            created = []

            def factory(config):
                lifecycle = FakeLifecycle(
                    config,
                    pid=300 + len(created),
                )
                created.append(lifecycle)
                return lifecycle

            manager = TextModelFallbackManager(
                gpu_config=gpu,
                cpu_config=cpu,
                selected_gpu_device="CUDA0",
                lifecycle_factory=factory,
            )
            snapshot = manager.load()

        self.assertEqual(
            snapshot.execution_mode,
            ModelExecutionMode.GPU,
        )
        self.assertFalse(snapshot.fallback_used)
        self.assertIsNone(snapshot.gpu_error)
        self.assertEqual(len(created), 1)

    def test_gpu_load_failure_falls_back_to_cpu(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base = self.config(root)
            gpu = build_gpu_config(
                base,
                device="CUDA0",
            )
            cpu = build_cpu_fallback_config(
                base
            )
            created = []

            def factory(config):
                lifecycle = FakeLifecycle(
                    config,
                    should_fail=(
                        config.device == "CUDA0"
                    ),
                    pid=400 + len(created),
                )
                created.append(lifecycle)
                return lifecycle

            manager = TextModelFallbackManager(
                gpu_config=gpu,
                cpu_config=cpu,
                selected_gpu_device="CUDA0",
                lifecycle_factory=factory,
            )
            snapshot = manager.load()

        self.assertEqual(len(created), 2)
        self.assertEqual(
            snapshot.execution_mode,
            ModelExecutionMode.CPU,
        )
        self.assertTrue(snapshot.fallback_used)
        self.assertIn(
            "simulated load failure",
            snapshot.gpu_error,
        )
        self.assertEqual(
            manager.active_lifecycle.config.device,
            "none",
        )

    def test_both_gpu_and_cpu_failure_are_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base = self.config(root)
            manager = TextModelFallbackManager(
                gpu_config=build_gpu_config(
                    base,
                    device="CUDA0",
                ),
                cpu_config=build_cpu_fallback_config(
                    base
                ),
                selected_gpu_device="CUDA0",
                lifecycle_factory=lambda config: FakeLifecycle(
                    config,
                    should_fail=True,
                ),
            )

            with self.assertRaises(
                ModelFallbackExhaustedError
            ) as captured:
                manager.load()

        self.assertIn(
            "simulated load failure",
            captured.exception.gpu_error,
        )
        self.assertIn(
            "simulated load failure",
            captured.exception.cpu_error,
        )

    def test_idle_ready_and_unload_delegate_to_active_backend(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base = self.config(root)
            created = []

            def factory(config):
                lifecycle = FakeLifecycle(
                    config,
                    pid=500,
                )
                created.append(lifecycle)
                return lifecycle

            manager = TextModelFallbackManager(
                gpu_config=None,
                cpu_config=build_cpu_fallback_config(
                    base
                ),
                lifecycle_factory=factory,
                gpu_unavailable_reason="no gpu",
            )
            manager.load()
            self.assertEqual(
                manager.mark_idle().state,
                ModelLifecycleState.IDLE,
            )
            self.assertEqual(
                manager.mark_ready().state,
                ModelLifecycleState.READY,
            )
            unloaded = manager.unload()

        self.assertEqual(
            unloaded.state,
            ModelLifecycleState.UNLOADED,
        )
        self.assertEqual(
            created[0].unload_calls,
            1,
        )
        self.assertIsNone(
            manager.execution_mode
        )

    def test_active_lifecycle_requires_loaded_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = self.config(Path(temp_dir))
            manager = TextModelFallbackManager(
                gpu_config=None,
                cpu_config=build_cpu_fallback_config(
                    base
                ),
            )

            with self.assertRaises(
                ModelFallbackError
            ):
                _ = manager.active_lifecycle


if __name__ == "__main__":
    unittest.main()
