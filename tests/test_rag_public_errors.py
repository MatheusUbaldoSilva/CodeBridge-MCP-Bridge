import unittest

from rag.models.lifecycle import ModelLoadError
from rag.runtime.context_service import (
    RagContextIndexUnavailableError,
    RagContextInvalidScopeError,
    RagContextSourceMissingError,
)
from rag.runtime.errors import (
    RagPublicErrorType,
    RagStaleResultError,
    classify_rag_error,
)
from rag.runtime.index_request import RagIndexExecutionUnavailableError
from rag.runtime.search_service import RagSearchIndexUnavailableError


class RagPublicErrorContractTests(unittest.TestCase):
    def assert_error(self, exc, expected_type, retryable):
        payload = classify_rag_error(exc)
        self.assertEqual(payload.error_type, expected_type)
        self.assertEqual(payload.retryable, retryable)
        self.assertTrue(payload.message)

    def test_model_load_error_contract(self):
        self.assert_error(
            ModelLoadError("model failed"),
            RagPublicErrorType.MODEL_LOAD,
            True,
        )

    def test_index_unavailable_error_contracts(self):
        self.assert_error(
            RagSearchIndexUnavailableError("missing search index"),
            RagPublicErrorType.INDEX_UNAVAILABLE,
            True,
        )
        self.assert_error(
            RagContextIndexUnavailableError("missing context index"),
            RagPublicErrorType.INDEX_UNAVAILABLE,
            True,
        )

    def test_source_missing_error_contract(self):
        self.assert_error(
            RagContextSourceMissingError("missing source"),
            RagPublicErrorType.SOURCE_MISSING,
            False,
        )

    def test_stale_result_error_contract(self):
        self.assert_error(
            RagStaleResultError("stale"),
            RagPublicErrorType.STALE_RESULT,
            False,
        )

    def test_invalid_scope_error_contract(self):
        self.assert_error(
            RagContextInvalidScopeError("invalid scope"),
            RagPublicErrorType.INVALID_SCOPE,
            False,
        )
        self.assert_error(
            ValueError("bad input"),
            RagPublicErrorType.INVALID_SCOPE,
            False,
        )

    def test_executor_unavailable_contract(self):
        self.assert_error(
            RagIndexExecutionUnavailableError("executor unavailable"),
            RagPublicErrorType.EXECUTOR_UNAVAILABLE,
            True,
        )

    def test_unknown_error_is_internal(self):
        self.assert_error(
            RuntimeError("unknown"),
            RagPublicErrorType.INTERNAL_ERROR,
            False,
        )


if __name__ == "__main__":
    unittest.main()
