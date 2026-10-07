import threading
import time
import unittest

from rag.runtime.model_manager import (
    ExclusiveModelManager,
    ManagedModel,
)


class BlockingRuntime:
    def __init__(self, name, events, *, block_load=False):
        self.name = name
        self.events = events
        self.block_load = block_load
        self.started = threading.Event()
        self.release = threading.Event()
        self._counter_lock = threading.Lock()
        self.active_loads = 0
        self.max_active_loads = 0
        self.load_calls = 0
        self.unload_calls = 0

    def load(self, **kwargs):
        with self._counter_lock:
            self.load_calls += 1
            self.active_loads += 1
            self.max_active_loads = max(
                self.max_active_loads,
                self.active_loads,
            )

        self.events.append((self.name, "load-start"))

        if self.block_load:
            self.started.set()
            if not self.release.wait(timeout=2):
                raise RuntimeError("test load release timeout")

        self.events.append((self.name, "load-end"))

        with self._counter_lock:
            self.active_loads -= 1

        return f"{self.name}-loaded"

    def unload(self, **kwargs):
        self.unload_calls += 1
        self.events.append((self.name, "unload"))
        return f"{self.name}-unloaded"


def run_thread(target, errors):
    try:
        target()
    except Exception as exc:
        errors.append(exc)


class RagModelManagerConcurrencyTests(unittest.TestCase):
    def test_two_same_model_loads_never_overlap(self):
        events = []
        errors = []
        text = BlockingRuntime("text", events, block_load=True)
        code = BlockingRuntime("code", events)
        manager = ExclusiveModelManager(
            text_runtime=text,
            code_runtime=code,
        )

        first = threading.Thread(
            target=lambda: run_thread(
                lambda: manager.activate(ManagedModel.TEXT),
                errors,
            )
        )
        second = threading.Thread(
            target=lambda: run_thread(
                lambda: manager.activate(ManagedModel.TEXT),
                errors,
            )
        )

        first.start()
        self.assertTrue(text.started.wait(timeout=1))
        second.start()

        time.sleep(0.05)

        self.assertEqual(text.load_calls, 1)
        self.assertEqual(text.max_active_loads, 1)
        self.assertTrue(second.is_alive())

        text.release.set()
        first.join(timeout=2)
        second.join(timeout=2)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(text.load_calls, 2)
        self.assertEqual(text.max_active_loads, 1)
        self.assertEqual(manager.active_model, ManagedModel.TEXT)

    def test_code_load_waits_for_text_load_then_switches_safely(self):
        events = []
        errors = []
        text = BlockingRuntime("text", events, block_load=True)
        code = BlockingRuntime("code", events)
        manager = ExclusiveModelManager(
            text_runtime=text,
            code_runtime=code,
        )

        first = threading.Thread(
            target=lambda: run_thread(
                lambda: manager.activate(ManagedModel.TEXT),
                errors,
            )
        )
        second = threading.Thread(
            target=lambda: run_thread(
                lambda: manager.activate(ManagedModel.CODE),
                errors,
            )
        )

        first.start()
        self.assertTrue(text.started.wait(timeout=1))
        second.start()

        time.sleep(0.05)

        self.assertEqual(code.load_calls, 0)
        self.assertEqual(text.unload_calls, 0)

        text.release.set()
        first.join(timeout=2)
        second.join(timeout=2)

        self.assertEqual(errors, [])
        self.assertEqual(
            events,
            [
                ("text", "load-start"),
                ("text", "load-end"),
                ("text", "unload"),
                ("code", "load-start"),
                ("code", "load-end"),
            ],
        )
        self.assertEqual(manager.active_model, ManagedModel.CODE)

    def test_unload_waits_for_inflight_load(self):
        events = []
        errors = []
        text = BlockingRuntime("text", events, block_load=True)
        code = BlockingRuntime("code", events)
        manager = ExclusiveModelManager(
            text_runtime=text,
            code_runtime=code,
        )

        loader = threading.Thread(
            target=lambda: run_thread(
                lambda: manager.activate(ManagedModel.TEXT),
                errors,
            )
        )
        unloader = threading.Thread(
            target=lambda: run_thread(
                manager.unload_active,
                errors,
            )
        )

        loader.start()
        self.assertTrue(text.started.wait(timeout=1))
        unloader.start()

        time.sleep(0.05)
        self.assertEqual(text.unload_calls, 0)

        text.release.set()
        loader.join(timeout=2)
        unloader.join(timeout=2)

        self.assertEqual(errors, [])
        self.assertEqual(
            events,
            [
                ("text", "load-start"),
                ("text", "load-end"),
                ("text", "unload"),
            ],
        )
        self.assertIsNone(manager.active_model)


if __name__ == "__main__":
    unittest.main()
