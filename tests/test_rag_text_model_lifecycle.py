import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.models.backend_policy import (
    SELECTED_TEXT_BACKEND,
)
from rag.models.lifecycle import (
    LlamaServerConfig,
    ModelLifecycleState,
    ModelLifecycleStateError,
    ModelLoadError,
    TextModelLifecycle,
    build_llama_server_argv,
)


class FakeProcess:
    def __init__(
        self,
        *,
        pid=4242,
        exit_code=None,
        timeout_on_first_wait=False,
    ):
        self.pid = pid
        self.exit_code = exit_code
        self.terminated = False
        self.killed = False
        self.wait_calls = 0
        self.timeout_on_first_wait = (
            timeout_on_first_wait
        )

    def poll(self):
        return self.exit_code

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True
        self.exit_code = -9

    def wait(self, timeout=None):
        self.wait_calls += 1
        if (
            self.timeout_on_first_wait
            and self.wait_calls == 1
        ):
            raise subprocess.TimeoutExpired(
                cmd="llama-server",
                timeout=timeout,
            )
        if self.exit_code is None:
            self.exit_code = 0
        return self.exit_code


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class RagTextModelLifecycleTests(unittest.TestCase):
    def make_model(self, root: Path) -> Path:
        pin = SELECTED_TEXT_BACKEND.artifact_pin
        path = root / str(pin.filename)

        # Lifecycle tests do not need the 397 MB production artifact.
        # Runtime input verification is patched at the method boundary
        # for process-state tests below.
        path.write_bytes(b"fixture")
        return path

    def config(
        self,
        root: Path,
        *,
        port=19077,
        gpu_layers=99,
    ):
        executable = root / "llama-server.exe"
        executable.write_bytes(b"fake")
        model = self.make_model(root)
        return LlamaServerConfig(
            executable_path=executable,
            model_path=model,
            port=port,
            gpu_layers=gpu_layers,
            log_path=root / "server.log",
        )

    def test_initial_state_is_unloaded_without_process(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = TextModelLifecycle(
                self.config(Path(temp_dir))
            )
            snapshot = manager.snapshot()

        self.assertEqual(
            snapshot.state,
            ModelLifecycleState.UNLOADED,
        )
        self.assertIsNone(snapshot.pid)
        self.assertFalse(snapshot.process_alive)

    def test_build_argv_is_shell_free_loopback_embedding_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config(Path(temp_dir))
            argv = build_llama_server_argv(
                config,
                resolved_port=19077,
            )

        self.assertEqual(
            argv[0],
            str(config.executable_path),
        )
        self.assertIn("--embedding", argv)
        self.assertIn("--pooling", argv)
        self.assertIn("last", argv)
        self.assertIn("--host", argv)
        self.assertIn("127.0.0.1", argv)
        self.assertIn("--port", argv)
        self.assertIn("19077", argv)
        self.assertIn("-ngl", argv)
        self.assertIn("99", argv)

    def test_non_loopback_bind_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaises(ValueError):
                LlamaServerConfig(
                    executable_path=root / "server.exe",
                    model_path=root / "model.gguf",
                    host="0.0.0.0",
                )

    def test_full_required_state_sequence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_process = FakeProcess()
            seen_kwargs = {}

            def factory(argv, **kwargs):
                seen_kwargs.update(kwargs)
                return fake_process

            manager = TextModelLifecycle(
                self.config(root),
                process_factory=factory,
                health_probe=lambda url, timeout: True,
            )
            manager._validate_runtime_inputs = lambda: None

            loaded = manager.load()
            self.assertEqual(
                loaded.state,
                ModelLifecycleState.READY,
            )
            self.assertEqual(loaded.pid, 4242)

            idle = manager.mark_idle()
            self.assertEqual(
                idle.state,
                ModelLifecycleState.IDLE,
            )

            unloaded = manager.unload()
            self.assertEqual(
                unloaded.state,
                ModelLifecycleState.UNLOADED,
            )

            self.assertEqual(
                manager.state_history,
                (
                    ModelLifecycleState.UNLOADED,
                    ModelLifecycleState.LOADING,
                    ModelLifecycleState.READY,
                    ModelLifecycleState.IDLE,
                    ModelLifecycleState.UNLOADING,
                    ModelLifecycleState.UNLOADED,
                ),
            )
            self.assertTrue(fake_process.terminated)
            self.assertFalse(seen_kwargs["shell"])

    def test_idle_can_return_to_ready_without_new_process(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_process = FakeProcess()
            starts = 0

            def factory(argv, **kwargs):
                nonlocal starts
                starts += 1
                return fake_process

            manager = TextModelLifecycle(
                self.config(root),
                process_factory=factory,
                health_probe=lambda url, timeout: True,
            )
            manager._validate_runtime_inputs = lambda: None

            manager.load()
            manager.mark_idle()
            snapshot = manager.mark_ready()

            self.assertEqual(
                snapshot.state,
                ModelLifecycleState.READY,
            )
            self.assertEqual(starts, 1)
            manager.unload()

    def test_load_from_ready_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_process = FakeProcess()
            starts = 0

            def factory(argv, **kwargs):
                nonlocal starts
                starts += 1
                return fake_process

            manager = TextModelLifecycle(
                self.config(root),
                process_factory=factory,
                health_probe=lambda url, timeout: True,
            )
            manager._validate_runtime_inputs = lambda: None

            first = manager.load()
            second = manager.load()

            self.assertEqual(first.pid, second.pid)
            self.assertEqual(starts, 1)
            manager.unload()

    def test_unload_from_unloaded_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = TextModelLifecycle(
                self.config(Path(temp_dir))
            )
            snapshot = manager.unload()

        self.assertEqual(
            snapshot.state,
            ModelLifecycleState.UNLOADED,
        )

    def test_health_is_polled_until_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_process = FakeProcess()
            clock = FakeClock()
            answers = iter((False, False, True))
            calls = []

            def health(url, timeout):
                calls.append((url, timeout))
                return next(answers)

            manager = TextModelLifecycle(
                self.config(root),
                process_factory=lambda *a, **k: fake_process,
                health_probe=health,
                clock=clock,
                sleeper=clock.sleep,
            )
            manager._validate_runtime_inputs = lambda: None

            snapshot = manager.load(
                timeout_seconds=5,
                poll_interval_seconds=0.25,
                health_timeout_seconds=0.5,
            )

            self.assertEqual(
                snapshot.state,
                ModelLifecycleState.READY,
            )
            self.assertEqual(len(calls), 3)
            self.assertEqual(
                snapshot.health_url,
                "http://127.0.0.1:19077/health",
            )
            manager.unload()

    def test_automatic_port_allocator_is_used_when_port_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_process = FakeProcess()
            captured = []

            def factory(argv, **kwargs):
                captured.extend(argv)
                return fake_process

            manager = TextModelLifecycle(
                self.config(root, port=0),
                process_factory=factory,
                health_probe=lambda url, timeout: True,
                port_allocator=lambda: 32123,
            )
            manager._validate_runtime_inputs = lambda: None

            snapshot = manager.load()

            self.assertEqual(snapshot.port, 32123)
            self.assertIn("32123", captured)
            manager.unload()

    def test_process_exit_before_health_rolls_back_to_unloaded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_process = FakeProcess(
                exit_code=3,
            )
            manager = TextModelLifecycle(
                self.config(root),
                process_factory=lambda *a, **k: fake_process,
                health_probe=lambda url, timeout: False,
            )
            manager._validate_runtime_inputs = lambda: None

            with self.assertRaisesRegex(
                ModelLoadError,
                "exited before health",
            ):
                manager.load()

            self.assertEqual(
                manager.state,
                ModelLifecycleState.UNLOADED,
            )
            self.assertIsNone(
                manager.snapshot().pid
            )

    def test_health_timeout_terminates_process_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_process = FakeProcess()
            clock = FakeClock()

            manager = TextModelLifecycle(
                self.config(root),
                process_factory=lambda *a, **k: fake_process,
                health_probe=lambda url, timeout: False,
                clock=clock,
                sleeper=clock.sleep,
            )
            manager._validate_runtime_inputs = lambda: None

            with self.assertRaisesRegex(
                ModelLoadError,
                "timed out",
            ):
                manager.load(
                    timeout_seconds=0.5,
                    poll_interval_seconds=0.25,
                )

            self.assertTrue(fake_process.terminated)
            self.assertEqual(
                manager.state,
                ModelLifecycleState.UNLOADED,
            )

    def test_unload_escalates_to_kill_after_terminate_timeout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_process = FakeProcess(
                timeout_on_first_wait=True,
            )
            manager = TextModelLifecycle(
                self.config(root),
                process_factory=lambda *a, **k: fake_process,
                health_probe=lambda url, timeout: True,
            )
            manager._validate_runtime_inputs = lambda: None

            manager.load()
            manager.unload(
                timeout_seconds=0.1,
            )

            self.assertTrue(fake_process.terminated)
            self.assertTrue(fake_process.killed)
            self.assertEqual(
                manager.state,
                ModelLifecycleState.UNLOADED,
            )

    def test_invalid_state_transitions_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = TextModelLifecycle(
                self.config(Path(temp_dir))
            )

            with self.assertRaises(
                ModelLifecycleStateError
            ):
                manager.mark_idle()

            with self.assertRaises(
                ModelLifecycleStateError
            ):
                manager.mark_ready()

    def test_runtime_validation_rejects_missing_executable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = LlamaServerConfig(
                executable_path=root / "missing.exe",
                model_path=root / "missing.gguf",
                port=19077,
                log_path=root / "server.log",
            )
            manager = TextModelLifecycle(config)

            with self.assertRaisesRegex(
                ModelLoadError,
                "executable",
            ):
                manager.load()

    def test_runtime_validation_uses_pinned_model_verification(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = self.config(root)
            manager = TextModelLifecycle(config)

            with self.assertRaisesRegex(
                ModelLoadError,
                "artifact",
            ):
                manager.load()

    def test_no_process_is_created_on_import_or_constructor(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            starts = 0

            def factory(argv, **kwargs):
                nonlocal starts
                starts += 1
                return FakeProcess()

            TextModelLifecycle(
                self.config(root),
                process_factory=factory,
            )

            self.assertEqual(starts, 0)


if __name__ == "__main__":
    unittest.main()
