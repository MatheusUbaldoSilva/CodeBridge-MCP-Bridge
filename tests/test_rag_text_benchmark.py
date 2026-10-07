import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.models.benchmark import TextRuntimeBenchmark, benchmark_text_runtime
from rag.models.fallback import (
    ModelExecutionMode,
    TextModelFallbackManager,
    build_cpu_fallback_config,
)
from rag.models.lifecycle import (
    LlamaServerConfig,
    ModelLifecycleSnapshot,
    ModelLifecycleState,
)


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        self.value += 0.01
        return self.value


class FakeLifecycle:
    def __init__(self, config):
        self.config = config
        self.state = ModelLifecycleState.UNLOADED
        self.pid = 1234

    def load(self, **kwargs):
        self.state = ModelLifecycleState.READY
        return self.snapshot()

    def snapshot(self):
        loaded = self.state is not ModelLifecycleState.UNLOADED
        return ModelLifecycleSnapshot(
            state=self.state,
            pid=self.pid if loaded else None,
            host="127.0.0.1",
            port=19120 if loaded else None,
            health_url="http://127.0.0.1:19120/health" if loaded else None,
            executable_path=self.config.executable_path,
            model_path=self.config.model_path,
            process_alive=loaded,
        )

    def unload(self, **kwargs):
        self.state = ModelLifecycleState.UNLOADED
        return self.snapshot()


class FakeClient:
    def __init__(self, lifecycle):
        self.lifecycle = lifecycle

    def embed_query(self, text):
        return object()

    def embed_document(self, text):
        return object()


class BenchmarkTests(unittest.TestCase):
    def test_result_rejects_invalid_samples(self):
        with self.assertRaises(ValueError):
            TextRuntimeBenchmark(
                ModelExecutionMode.GPU,
                1,
                2,
                3,
                4,
                5,
                6,
                0,
                1,
            )

    def test_benchmark_records_required_axes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            executable = root / "server.exe"
            model = root / "model.gguf"
            executable.write_bytes(b"x")
            model.write_bytes(b"x")
            base = LlamaServerConfig(
                executable_path=executable,
                model_path=model,
                device="CUDA0",
                gpu_layers=99,
            )
            manager = TextModelFallbackManager(
                gpu_config=base,
                cpu_config=build_cpu_fallback_config(base),
                selected_gpu_device="CUDA0",
                lifecycle_factory=FakeLifecycle,
            )
            vram = iter((100, 140))
            result = benchmark_text_runtime(
                manager,
                query_text="query",
                document_texts=("a", "b", "c"),
                warm_query_samples=2,
                ram_probe=lambda pid: 123456,
                vram_probe=lambda: next(vram),
                clock=FakeClock(),
                client_factory=FakeClient,
            )

        self.assertEqual(
            result.execution_mode,
            ModelExecutionMode.GPU,
        )
        self.assertEqual(
            result.ram_working_set_bytes,
            123456,
        )
        self.assertEqual(
            result.vram_delta_mib,
            40,
        )
        self.assertEqual(
            result.warm_query_samples,
            2,
        )
        self.assertEqual(
            result.throughput_samples,
            3,
        )
        self.assertGreater(
            result.embeddings_per_second,
            0,
        )

    def test_invalid_inputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            executable = root / "server.exe"
            model = root / "model.gguf"
            executable.write_bytes(b"x")
            model.write_bytes(b"x")
            base = LlamaServerConfig(
                executable_path=executable,
                model_path=model,
            )
            manager = TextModelFallbackManager(
                gpu_config=None,
                cpu_config=build_cpu_fallback_config(base),
                lifecycle_factory=FakeLifecycle,
            )

            with self.assertRaises(ValueError):
                benchmark_text_runtime(
                    manager,
                    query_text="",
                    document_texts=("x",),
                )

            with self.assertRaises(ValueError):
                benchmark_text_runtime(
                    manager,
                    query_text="x",
                    document_texts=(),
                )


if __name__ == "__main__":
    unittest.main()
