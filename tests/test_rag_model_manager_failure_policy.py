import unittest

from rag.runtime.model_manager import (
    ExclusiveModelManager,
    ManagedModel,
    ModelManagerErrorType,
    ModelManagerOperation,
)
from rag.runtime.query_classifier import QueryRoute


class FakeRuntime:
    def __init__(
        self,
        name,
        events,
        *,
        fail_load=False,
        fail_unload=False,
    ):
        self.name = name
        self.events = events
        self.fail_load = fail_load
        self.fail_unload = fail_unload
        self.load_calls = 0
        self.unload_calls = 0

    def load(self, **kwargs):
        self.load_calls += 1
        self.events.append((self.name, "load"))
        if self.fail_load:
            raise RuntimeError(f"{self.name} load exploded")
        return f"{self.name}-loaded"

    def unload(self, **kwargs):
        self.unload_calls += 1
        self.events.append((self.name, "unload"))
        if self.fail_unload:
            raise RuntimeError(f"{self.name} unload exploded")
        return f"{self.name}-unloaded"


class RagModelManagerFailurePolicyTests(unittest.TestCase):
    def test_safe_activation_success_is_structured(self):
        events = []
        text = FakeRuntime("text", events)
        code = FakeRuntime("code", events)
        manager = ExclusiveModelManager(
            text_runtime=text,
            code_runtime=code,
        )

        result = manager.activate_safe(ManagedModel.TEXT)

        self.assertTrue(result.ok)
        self.assertEqual(result.operation, ModelManagerOperation.ACTIVATE)
        self.assertEqual(result.requested_model, ManagedModel.TEXT)
        self.assertEqual(result.active_model, ManagedModel.TEXT)
        self.assertEqual(result.value, "text-loaded")
        self.assertIsNone(result.error_type)
        self.assertIsNone(result.fallback_route)
        self.assertTrue(result.resources_released)

    def test_failed_load_returns_lexical_fallback_without_raising(self):
        events = []
        text = FakeRuntime("text", events)
        code = FakeRuntime("code", events, fail_load=True)
        manager = ExclusiveModelManager(
            text_runtime=text,
            code_runtime=code,
        )

        result = manager.activate_safe(ManagedModel.CODE)

        self.assertFalse(result.ok)
        self.assertEqual(
            result.error_type,
            ModelManagerErrorType.ACTIVATION_FAILED,
        )
        self.assertEqual(result.cause_type, "RuntimeError")
        self.assertIn("code load exploded", result.error_message)
        self.assertEqual(result.fallback_route, QueryRoute.LEXICAL_ONLY)
        self.assertIsNone(result.active_model)
        self.assertIsNone(manager.active_model)
        self.assertEqual(result.cleanup_errors, ())
        self.assertTrue(result.resources_released)
        self.assertEqual(text.unload_calls, 1)
        self.assertEqual(code.unload_calls, 1)

    def test_switch_unload_failure_is_structured_and_cleanup_is_attempted(self):
        events = []
        text = FakeRuntime("text", events)
        code = FakeRuntime("code", events)
        manager = ExclusiveModelManager(
            text_runtime=text,
            code_runtime=code,
        )
        manager.activate(ManagedModel.TEXT)
        text.fail_unload = True

        result = manager.activate_safe(ManagedModel.CODE)

        self.assertFalse(result.ok)
        self.assertEqual(
            result.error_type,
            ModelManagerErrorType.ACTIVATION_FAILED,
        )
        self.assertEqual(result.fallback_route, QueryRoute.LEXICAL_ONLY)
        self.assertIsNone(manager.active_model)
        self.assertEqual(code.load_calls, 0)
        self.assertGreaterEqual(text.unload_calls, 2)
        self.assertEqual(code.unload_calls, 1)
        self.assertFalse(result.resources_released)
        self.assertEqual(len(result.cleanup_errors), 1)
        self.assertIn("TEXT:RuntimeError", result.cleanup_errors[0])

    def test_cleanup_failure_is_reported_not_raised(self):
        events = []
        text = FakeRuntime("text", events)
        code = FakeRuntime(
            "code",
            events,
            fail_load=True,
            fail_unload=True,
        )
        manager = ExclusiveModelManager(
            text_runtime=text,
            code_runtime=code,
        )

        result = manager.activate_safe(ManagedModel.CODE)

        self.assertFalse(result.ok)
        self.assertEqual(result.fallback_route, QueryRoute.LEXICAL_ONLY)
        self.assertFalse(result.resources_released)
        self.assertEqual(len(result.cleanup_errors), 1)
        self.assertIn("CODE:RuntimeError", result.cleanup_errors[0])
        self.assertIsNone(manager.active_model)

    def test_safe_unload_success_is_structured(self):
        events = []
        text = FakeRuntime("text", events)
        code = FakeRuntime("code", events)
        manager = ExclusiveModelManager(
            text_runtime=text,
            code_runtime=code,
        )
        manager.activate(ManagedModel.TEXT)

        result = manager.unload_active_safe()

        self.assertTrue(result.ok)
        self.assertEqual(result.operation, ModelManagerOperation.UNLOAD)
        self.assertEqual(result.requested_model, ManagedModel.TEXT)
        self.assertIsNone(result.active_model)
        self.assertIsNone(result.fallback_route)
        self.assertIsNone(manager.active_model)

    def test_safe_unload_failure_returns_lexical_fallback(self):
        events = []
        text = FakeRuntime("text", events, fail_unload=True)
        code = FakeRuntime("code", events)
        manager = ExclusiveModelManager(
            text_runtime=text,
            code_runtime=code,
        )
        manager.activate(ManagedModel.TEXT)

        result = manager.unload_active_safe()

        self.assertFalse(result.ok)
        self.assertEqual(
            result.error_type,
            ModelManagerErrorType.UNLOAD_FAILED,
        )
        self.assertEqual(result.fallback_route, QueryRoute.LEXICAL_ONLY)
        self.assertIsNone(manager.active_model)
        self.assertFalse(result.resources_released)
        self.assertTrue(result.cleanup_errors)

    def test_safe_activation_keeps_programming_errors_explicit(self):
        events = []
        manager = ExclusiveModelManager(
            text_runtime=FakeRuntime("text", events),
            code_runtime=FakeRuntime("code", events),
        )

        with self.assertRaises(ValueError):
            manager.activate_safe("TEXT")


if __name__ == "__main__":
    unittest.main()
