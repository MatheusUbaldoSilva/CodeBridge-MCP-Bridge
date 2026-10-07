import unittest

from rag.runtime.model_manager import (
    ExclusiveModelManager,
    ManagedModel,
)


class FakeClock:
    def __init__(self, value=0.0):
        self.value = float(value)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += float(seconds)


class FakeRuntime:
    def __init__(self, name, events):
        self.name = name
        self.events = events
        self.load_calls = 0
        self.unload_calls = 0

    def load(self, **kwargs):
        self.load_calls += 1
        self.events.append((self.name, "load", kwargs))
        return f"{self.name}-loaded"

    def unload(self, **kwargs):
        self.unload_calls += 1
        self.events.append((self.name, "unload", kwargs))
        return f"{self.name}-unloaded"


class RagModelManagerIdleTimeoutTests(unittest.TestCase):
    def make_manager(self, timeout=60.0):
        events = []
        clock = FakeClock(100.0)
        text = FakeRuntime("text", events)
        code = FakeRuntime("code", events)
        manager = ExclusiveModelManager(
            text_runtime=text,
            code_runtime=code,
            idle_timeout_seconds=timeout,
            clock=clock,
        )
        return manager, text, code, events, clock

    def test_timeout_is_configurable(self):
        manager, _, _, _, _ = self.make_manager(timeout=45)
        self.assertEqual(manager.idle_timeout_seconds, 45.0)

    def test_invalid_timeout_is_rejected(self):
        events = []
        runtime_a = FakeRuntime("a", events)
        runtime_b = FakeRuntime("b", events)

        for value in (0, -1):
            with self.assertRaises(ValueError):
                ExclusiveModelManager(
                    text_runtime=runtime_a,
                    code_runtime=runtime_b,
                    idle_timeout_seconds=value,
                )

    def test_activation_records_activity(self):
        manager, _, _, _, clock = self.make_manager()
        manager.activate(ManagedModel.TEXT)

        self.assertEqual(manager.last_activity_at, 100.0)
        self.assertEqual(manager.idle_seconds(), 0.0)

        clock.advance(12.5)
        self.assertEqual(manager.idle_seconds(), 12.5)

    def test_touch_refreshes_idle_deadline(self):
        manager, _, _, _, clock = self.make_manager(timeout=60)
        manager.activate(ManagedModel.TEXT)
        clock.advance(50)

        touched = manager.touch()

        self.assertEqual(touched, 150.0)
        clock.advance(20)
        self.assertEqual(manager.idle_seconds(), 20.0)
        self.assertFalse(manager.unload_if_idle())

    def test_touch_requires_active_model(self):
        manager, _, _, _, _ = self.make_manager()

        with self.assertRaises(RuntimeError):
            manager.touch()

    def test_before_timeout_model_stays_loaded(self):
        manager, text, _, _, clock = self.make_manager(timeout=30)
        manager.activate(ManagedModel.TEXT)
        clock.advance(29.999)

        self.assertFalse(manager.unload_if_idle())
        self.assertEqual(manager.active_model, ManagedModel.TEXT)
        self.assertEqual(text.unload_calls, 0)

    def test_at_timeout_active_model_is_unloaded(self):
        manager, text, _, events, clock = self.make_manager(timeout=30)
        manager.activate(ManagedModel.TEXT)
        clock.advance(30)

        self.assertTrue(
            manager.unload_if_idle(
                unload_kwargs={"timeout_seconds": 15},
            )
        )
        self.assertIsNone(manager.active_model)
        self.assertIsNone(manager.last_activity_at)
        self.assertEqual(text.unload_calls, 1)
        self.assertEqual(
            events[-1],
            ("text", "unload", {"timeout_seconds": 15}),
        )

    def test_timeout_applies_to_code_model_too(self):
        manager, _, code, _, clock = self.make_manager(timeout=10)
        manager.activate(ManagedModel.CODE)
        clock.advance(11)

        self.assertTrue(manager.unload_if_idle())
        self.assertEqual(code.unload_calls, 1)
        self.assertIsNone(manager.active_model)

    def test_disabled_timeout_never_unloads_automatically(self):
        events = []
        clock = FakeClock(10)
        text = FakeRuntime("text", events)
        code = FakeRuntime("code", events)
        manager = ExclusiveModelManager(
            text_runtime=text,
            code_runtime=code,
            idle_timeout_seconds=None,
            clock=clock,
        )
        manager.activate(ManagedModel.TEXT)
        clock.advance(99999)

        self.assertFalse(manager.unload_if_idle())
        self.assertEqual(manager.active_model, ManagedModel.TEXT)
        self.assertEqual(text.unload_calls, 0)

    def test_switching_models_resets_activity_timestamp(self):
        manager, _, _, _, clock = self.make_manager(timeout=60)
        manager.activate(ManagedModel.TEXT)
        clock.advance(40)
        manager.activate(ManagedModel.CODE)

        self.assertEqual(manager.last_activity_at, 140.0)
        self.assertEqual(manager.idle_seconds(), 0.0)

    def test_reactivating_same_model_refreshes_activity(self):
        manager, text, _, _, clock = self.make_manager(timeout=60)
        manager.activate(ManagedModel.TEXT)
        clock.advance(50)
        manager.activate(ManagedModel.TEXT)

        self.assertEqual(text.load_calls, 2)
        self.assertEqual(manager.last_activity_at, 150.0)

    def test_unload_active_clears_activity_timestamp(self):
        manager, _, _, _, _ = self.make_manager()
        manager.activate(ManagedModel.TEXT)
        manager.unload_active()

        self.assertIsNone(manager.last_activity_at)
        self.assertIsNone(manager.idle_seconds())

    def test_explicit_now_makes_sweep_deterministic(self):
        manager, text, _, _, _ = self.make_manager(timeout=25)
        manager.activate(ManagedModel.TEXT)

        self.assertFalse(manager.unload_if_idle(now=124.9))
        self.assertTrue(manager.unload_if_idle(now=125.0))
        self.assertEqual(text.unload_calls, 1)


if __name__ == "__main__":
    unittest.main()
