import ast
import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.models.backend_policy import (
    BACKEND_EVALUATIONS,
    SELECTED_TEXT_BACKEND,
    TEXT_MODEL_FAMILY,
    TEXT_MODEL_LICENSE,
    TEXT_RETRIEVAL_REPOSITORY,
    DistributionMode,
    InferenceBackend,
    selected_backend_evaluation,
)


class RagTextBackendPolicyTests(unittest.TestCase):
    def test_llama_cpp_http_is_the_single_selected_backend(self):
        selected = [
            item.backend
            for item in BACKEND_EVALUATIONS
            if item.selected
        ]
        self.assertEqual(
            selected,
            [InferenceBackend.LLAMA_CPP_HTTP],
        )
        self.assertEqual(
            selected_backend_evaluation().backend,
            InferenceBackend.LLAMA_CPP_HTTP,
        )

    def test_all_evaluated_backends_cover_required_platform_axes(self):
        for item in BACKEND_EVALUATIONS:
            with self.subTest(backend=item.backend):
                self.assertTrue(item.gpu_supported)
                self.assertTrue(item.cpu_supported)
                self.assertTrue(item.windows_supported)
                self.assertTrue(
                    item.distributable_with_codebridge
                )

    def test_selected_backend_avoids_python_ml_runtime_dependency(self):
        selected = selected_backend_evaluation()
        self.assertFalse(
            selected.requires_python_ml_stack
        )
        alternatives = {
            item.backend: item
            for item in BACKEND_EVALUATIONS
            if not item.selected
        }
        self.assertTrue(
            alternatives[
                InferenceBackend.PYTORCH_SENTENCE_TRANSFORMERS
            ].requires_python_ml_stack
        )
        self.assertTrue(
            alternatives[
                InferenceBackend.ONNX_RUNTIME_OPTIMUM
            ].requires_python_ml_stack
        )

    def test_retrieval_specific_jina_repository_is_frozen(self):
        self.assertEqual(
            TEXT_MODEL_FAMILY,
            "jinaai/jina-embeddings-v5-text-small",
        )
        self.assertEqual(
            TEXT_RETRIEVAL_REPOSITORY,
            "jinaai/jina-embeddings-v5-text-small-retrieval",
        )
        self.assertEqual(
            SELECTED_TEXT_BACKEND.model_repository,
            TEXT_RETRIEVAL_REPOSITORY,
        )
        self.assertEqual(
            SELECTED_TEXT_BACKEND.task,
            "retrieval",
        )

    def test_selected_transport_is_local_openai_compatible_http(self):
        policy = SELECTED_TEXT_BACKEND
        self.assertEqual(
            policy.transport,
            "HTTP_OPENAI_COMPATIBLE",
        )
        self.assertEqual(
            policy.host,
            "127.0.0.1",
        )
        self.assertEqual(
            policy.embeddings_endpoint,
            "/v1/embeddings",
        )
        self.assertEqual(
            policy.health_endpoint,
            "/health",
        )

    def test_selected_backend_uses_gguf_and_last_token_pooling(self):
        policy = SELECTED_TEXT_BACKEND
        self.assertEqual(
            policy.artifact_format,
            "GGUF",
        )
        self.assertEqual(
            policy.pooling,
            "last",
        )

    def test_retrieval_prompt_roles_are_explicit(self):
        policy = SELECTED_TEXT_BACKEND
        self.assertEqual(
            policy.query_prefix,
            "Query: ",
        )
        self.assertEqual(
            policy.document_prefix,
            "Document: ",
        )

    def test_gpu_is_preferred_but_cpu_fallback_is_mandatory(self):
        policy = SELECTED_TEXT_BACKEND
        self.assertTrue(policy.gpu_preferred)
        self.assertTrue(
            policy.cpu_fallback_required
        )
        self.assertTrue(policy.windows_required)

    def test_distribution_is_sidecar_not_python_environment(self):
        self.assertEqual(
            SELECTED_TEXT_BACKEND.distribution_mode,
            DistributionMode.BUNDLED_SIDECAR,
        )

    def test_rag_006_b_pins_artifact_but_keeps_auto_download_off(self):
        pin = SELECTED_TEXT_BACKEND.artifact_pin
        self.assertTrue(pin.is_fully_pinned)
        self.assertIsNotNone(pin.revision)
        self.assertIsNotNone(pin.filename)
        self.assertIsNotNone(pin.sha256)
        self.assertIsNotNone(pin.size_bytes)
        self.assertIsNotNone(pin.quantization)
        self.assertFalse(pin.download_allowed)
        self.assertFalse(
            SELECTED_TEXT_BACKEND.auto_download_allowed
        )
        self.assertFalse(
            SELECTED_TEXT_BACKEND.model_bundling_allowed
        )

    def test_license_gate_is_explicit_before_distribution(self):
        self.assertEqual(
            TEXT_MODEL_LICENSE,
            "CC-BY-NC-4.0",
        )
        self.assertEqual(
            SELECTED_TEXT_BACKEND.model_license,
            TEXT_MODEL_LICENSE,
        )
        self.assertTrue(
            SELECTED_TEXT_BACKEND
            .commercial_license_review_required
        )

    def test_policy_import_does_not_load_optional_ml_packages(self):
        before = set(sys.modules)
        import rag.models.backend_policy as module

        importlib.reload(module)
        newly_loaded = set(sys.modules).difference(before)

        forbidden_roots = {
            "torch",
            "transformers",
            "sentence_transformers",
            "onnxruntime",
            "optimum",
            "llama_cpp",
        }
        loaded_roots = {
            name.split(".", 1)[0]
            for name in newly_loaded
        }
        self.assertTrue(
            forbidden_roots.isdisjoint(loaded_roots)
        )

    def test_policy_import_has_no_network_or_process_dependency(self):
        import rag.models.backend_policy as module

        source = Path(
            module.__file__
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)

        imported_roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0]
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_roots.add(
                        node.module.split(".", 1)[0]
                    )

        forbidden_roots = {
            "subprocess",
            "requests",
            "urllib",
            "socket",
            "huggingface_hub",
        }
        self.assertTrue(
            forbidden_roots.isdisjoint(imported_roots)
        )


if __name__ == "__main__":
    unittest.main()
