import unittest

from rag.runtime.model_manager import (
    ExclusiveModelManager,
    ManagedModel,
    ModelManagerSnapshot,
)


class FakeRuntime:
    def __init__(self, name, events, *, fail_load=False, fail_unload=False):
        self.name = name
        self.events = events
        self.fail_load = fail_load
        self.fail_unload = fail_unload
        self.load_calls = 0
        self.unload_calls = 0

    def load(self, **kwargs):
        self.load_calls += 1
        self.events.append((self.name, "load", kwargs))
        if self.fail_load:
            raise RuntimeError(f"{self.name} load failed")
        return f"{self.name}-loaded"

    def unload(self, **kwargs):
        self.unload_calls += 1
        self.events.append((self.name, "unload", kwargs))
        if self.fail_unload:
            raise RuntimeError(f"{self.name} unload failed")
        return f"{self.name}-unloaded"


class RagModelManagerMutualExclusionTests(unittest.TestCase):
    def make_manager(self):
        events = []
        text = FakeRuntime("text", events)
        code = FakeRuntime("code", events)
        manager = ExclusiveModelManager(
            text_runtime=text,
            code_runtime=code,
        )
        return manager, text, code, events

    def test_initial_state_has_no_resident_model(self):
        manager, _, _, _ = self.make_manager()
        self.assertIsNone(manager.active_model)
        self.assertEqual(
            manager.snapshot(),
            ModelManagerSnapshot(
                active_model=None,
                text_loaded=False,
                code_loaded=False,
            ),
        )

    def test_activate_text_loads_only_text(self):
        manager, text, code, events = self.make_manager()
        result = manager.activate(ManagedModel.TEXT)

        self.assertEqual(result, "text-loaded")
        self.assertEqual(manager.active_model, ManagedModel.TEXT)
        self.assertEqual(text.load_calls, 1)
        self.assertEqual(code.load_calls, 0)
        self.assertEqual(events, [("text", "load", {})])

    def test_switch_text_to_code_unloads_text_before_code_load(self):
        manager, _, _, events = self.make_manager()
        manager.activate(ManagedModel.TEXT)
        manager.activate(ManagedModel.CODE)

        self.assertEqual(
            events,
            [
                ("text", "load", {}),
                ("text", "unload", {}),
                ("code", "load", {}),
            ],
        )
        self.assertEqual(manager.active_model, ManagedModel.CODE)
        self.assertFalse(manager.snapshot().text_loaded)
        self.assertTrue(manager.snapshot().code_loaded)

    def test_switch_code_to_text_unloads_code_before_text_load(self):
        manager, _, _, events = self.make_manager()
        manager.activate(ManagedModel.CODE)
        manager.activate(ManagedModel.TEXT)

        self.assertEqual(
            events,
            [
                ("code", "load", {}),
                ("code", "unload", {}),
                ("text", "load", {}),
            ],
        )
        self.assertEqual(manager.active_model, ManagedModel.TEXT)

    def test_reactivating_same_model_does_not_touch_other_runtime(self):
        manager, text, code, events = self.make_manager()
        manager.activate(ManagedModel.TEXT)
        manager.activate(ManagedModel.TEXT, load_kwargs={"timeout_seconds": 30})

        self.assertEqual(text.load_calls, 2)
        self.assertEqual(text.unload_calls, 0)
        self.assertEqual(code.load_calls, 0)
        self.assertEqual(
            events[-1],
            ("text", "load", {"timeout_seconds": 30}),
        )

    def test_load_failure_after_switch_leaves_no_active_model(self):
        events = []
        text = FakeRuntime("text", events)
        code = FakeRuntime("code", events, fail_load=True)
        manager = ExclusiveModelManager(
            text_runtime=text,
            code_runtime=code,
        )

        manager.activate(ManagedModel.TEXT)

        with self.assertRaises(RuntimeError):
            manager.activate(ManagedModel.CODE)

        self.assertEqual(
            events,
            [
                ("text", "load", {}),
                ("text", "unload", {}),
                ("code", "load", {}),
            ],
        )
        self.assertIsNone(manager.active_model)
        self.assertEqual(
            manager.snapshot(),
            ModelManagerSnapshot(
                active_model=None,
                text_loaded=False,
                code_loaded=False,
            ),
        )

    def test_unload_active_clears_residency(self):
        manager, text, _, events = self.make_manager()
        manager.activate(ManagedModel.TEXT)
        result = manager.unload_active(
            unload_kwargs={"timeout_seconds": 15},
        )

        self.assertEqual(result, "text-unloaded")
        self.assertIsNone(manager.active_model)
        self.assertEqual(text.unload_calls, 1)
        self.assertEqual(
            events[-1],
            ("text", "unload", {"timeout_seconds": 15}),
        )

    def test_unload_failure_still_clears_manager_state(self):
        events = []
        text = FakeRuntime("text", events, fail_unload=True)
        code = FakeRuntime("code", events)
        manager = ExclusiveModelManager(
            text_runtime=text,
            code_runtime=code,
        )
        manager.activate(ManagedModel.TEXT)

        with self.assertRaises(RuntimeError):
            manager.unload_active()

        self.assertIsNone(manager.active_model)

    def test_same_runtime_object_is_rejected(self):
        events = []
        runtime = FakeRuntime("shared", events)

        with self.assertRaises(ValueError):
            ExclusiveModelManager(
                text_runtime=runtime,
                code_runtime=runtime,
            )

    def test_invalid_model_is_rejected(self):
        manager, _, _, _ = self.make_manager()

        with self.assertRaises(ValueError):
            manager.activate("TEXT")

    def test_snapshot_rejects_double_residency(self):
        with self.assertRaises(ValueError):
            ModelManagerSnapshot(
                active_model=ManagedModel.TEXT,
                text_loaded=True,
                code_loaded=True,
            )


if __name__ == "__main__":
    unittest.main()
