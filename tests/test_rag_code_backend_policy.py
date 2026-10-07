import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.models.backend_policy import (
    DistributionMode,
    InferenceBackend,
)
from rag.models.code_backend_policy import (
    CODE_GGUF_REPOSITORY,
    CODE_LLAMA_CPP_DOCUMENTED_DIMENSION,
    CODE_MAX_CONTEXT_TOKENS,
    CODE_REFERENCE_EMBEDDING_DIMENSION,
    CODE_RECOMMENDED_CONTEXT_TOKENS,
    CODE_RECOMMENDED_UBATCH_SIZE,
    CODE_TASK_INSTRUCTIONS,
    REQUIRED_LLAMA_CPP_CODE_FLAGS,
    SELECTED_CODE_BACKEND,
    CodeRetrievalTask,
    probe_llama_cpp_code_backend,
)


class FakeCompleted:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class RagCodeBackendPolicyTests(unittest.TestCase):
    def test_llama_cpp_http_is_selected(self):
        self.assertEqual(
            SELECTED_CODE_BACKEND.backend,
            InferenceBackend.LLAMA_CPP_HTTP,
        )
        self.assertEqual(
            SELECTED_CODE_BACKEND.distribution_mode,
            DistributionMode.BUNDLED_SIDECAR,
        )
        self.assertEqual(
            SELECTED_CODE_BACKEND.model_repository,
            CODE_GGUF_REPOSITORY,
        )

    def test_backend_uses_local_openai_compatible_embedding_endpoint(self):
        self.assertEqual(
            SELECTED_CODE_BACKEND.host,
            "127.0.0.1",
        )
        self.assertEqual(
            SELECTED_CODE_BACKEND.embeddings_endpoint,
            "/v1/embeddings",
        )
        self.assertEqual(
            SELECTED_CODE_BACKEND.pooling,
            "last",
        )

    def test_context_contract_matches_upstream_gguf_guidance(self):
        self.assertEqual(
            CODE_MAX_CONTEXT_TOKENS,
            32768,
        )
        self.assertEqual(
            CODE_RECOMMENDED_CONTEXT_TOKENS,
            8192,
        )
        self.assertEqual(
            CODE_RECOMMENDED_UBATCH_SIZE,
            8192,
        )

    def test_dimension_discrepancy_is_explicit_not_hidden(self):
        self.assertEqual(
            CODE_REFERENCE_EMBEDDING_DIMENSION,
            1536,
        )
        self.assertEqual(
            CODE_LLAMA_CPP_DOCUMENTED_DIMENSION,
            896,
        )
        self.assertTrue(
            SELECTED_CODE_BACKEND.dimension_probe_required
        )

    def test_artifact_is_not_pinned_or_downloadable_in_007_a(self):
        pin = SELECTED_CODE_BACKEND.artifact_pin
        self.assertFalse(pin.is_fully_pinned)
        self.assertFalse(pin.download_allowed)
        self.assertFalse(
            SELECTED_CODE_BACKEND.auto_download_allowed
        )
        self.assertFalse(
            SELECTED_CODE_BACKEND.model_bundling_allowed
        )

    def test_license_review_remains_required(self):
        self.assertEqual(
            SELECTED_CODE_BACKEND.model_license,
            "CC-BY-NC-4.0",
        )
        self.assertTrue(
            SELECTED_CODE_BACKEND.commercial_license_review_required
        )

    def test_nl2code_prefixes_are_frozen(self):
        task = CODE_TASK_INSTRUCTIONS[
            CodeRetrievalTask.NL2CODE
        ]
        self.assertEqual(
            task.query_prefix,
            "Find the most relevant code snippet given the following query:\n",
        )
        self.assertEqual(
            task.passage_prefix,
            "Candidate code snippet:\n",
        )

    def test_code2code_prefixes_are_frozen(self):
        task = CODE_TASK_INSTRUCTIONS[
            CodeRetrievalTask.CODE2CODE
        ]
        self.assertEqual(
            task.query_prefix,
            "Find an equivalent code snippet given the following code snippet:\n",
        )
        self.assertEqual(
            task.passage_prefix,
            "Candidate code snippet:\n",
        )

    def test_all_required_tasks_have_query_and_passage_prefixes(self):
        self.assertEqual(
            set(CODE_TASK_INSTRUCTIONS),
            set(CodeRetrievalTask),
        )
        for item in CODE_TASK_INSTRUCTIONS.values():
            self.assertTrue(item.query_prefix)
            self.assertTrue(item.passage_prefix)

    def test_probe_accepts_local_feature_complete_llama_cpp(self):
        with tempfile.TemporaryDirectory() as td:
            executable = Path(td) / "llama-server.exe"
            executable.write_bytes(b"x")
            calls = []

            def runner(argv, **kwargs):
                calls.append((argv, kwargs))
                if "--version" in argv:
                    return FakeCompleted(
                        stdout="version: test-build"
                    )
                return FakeCompleted(
                    stdout="\n".join(
                        REQUIRED_LLAMA_CPP_CODE_FLAGS
                    )
                )

            result = probe_llama_cpp_code_backend(
                executable,
                runner=runner,
            )

        self.assertTrue(result.compatible)
        self.assertEqual(result.missing_flags, ())
        self.assertEqual(
            result.supported_flags,
            REQUIRED_LLAMA_CPP_CODE_FLAGS,
        )
        self.assertIn("test-build", result.version_text)
        self.assertEqual(len(calls), 2)
        self.assertFalse(calls[0][1]["shell"])
        self.assertFalse(calls[1][1]["shell"])

    def test_probe_reports_missing_flag_instead_of_guessing(self):
        with tempfile.TemporaryDirectory() as td:
            executable = Path(td) / "llama-server.exe"
            executable.write_bytes(b"x")

            def runner(argv, **kwargs):
                if "--version" in argv:
                    return FakeCompleted(stdout="version")
                return FakeCompleted(
                    stdout="--embedding --pooling"
                )

            result = probe_llama_cpp_code_backend(
                executable,
                runner=runner,
            )

        self.assertFalse(result.compatible)
        self.assertIn(
            "--ctx-size",
            result.missing_flags,
        )

    def test_probe_has_no_model_or_network_argument(self):
        with tempfile.TemporaryDirectory() as td:
            executable = Path(td) / "llama-server.exe"
            executable.write_bytes(b"x")
            calls = []

            def runner(argv, **kwargs):
                calls.append(tuple(argv))
                if "--version" in argv:
                    return FakeCompleted(stdout="version")
                return FakeCompleted(
                    stdout=" ".join(
                        REQUIRED_LLAMA_CPP_CODE_FLAGS
                    )
                )

            probe_llama_cpp_code_backend(
                executable,
                runner=runner,
            )

        rendered = " ".join(
            " ".join(call)
            for call in calls
        )
        self.assertNotIn("--hf-repo jinaai", rendered)
        self.assertNotIn("-m ", rendered)


if __name__ == "__main__":
    unittest.main()
