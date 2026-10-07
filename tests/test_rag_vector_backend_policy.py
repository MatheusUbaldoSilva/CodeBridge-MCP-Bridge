import sys
import unittest

from rag.index.vector_backend_policy import (
    CandidateDecision,
    SELECTED_VECTOR_BACKEND,
    SELECTED_VECTOR_PACKAGE,
    SELECTED_VECTOR_PACKAGE_VERSION,
    VECTOR_BACKEND_AUTO_INSTALL_ALLOWED,
    VECTOR_BACKEND_EVALUATIONS,
    VECTOR_BACKEND_EXTERNAL_SERVER_REQUIRED,
    VECTOR_BACKEND_PERSISTED_LOCAL_MODE,
    VECTOR_BACKEND_SCOPE,
    VectorBackendEvaluation,
    VectorStorageBackend,
    selected_vector_backend_evaluation,
)


class RagVectorBackendPolicyTests(unittest.TestCase):
    def test_policy_import_does_not_load_qdrant_client(self):
        self.assertNotIn("qdrant_client", sys.modules)

    def test_three_candidates_are_compared(self):
        self.assertEqual(
            {item.backend for item in VECTOR_BACKEND_EVALUATIONS},
            {
                VectorStorageBackend.QDRANT_LOCAL,
                VectorStorageBackend.SQLITE_VEC,
                VectorStorageBackend.LANCEDB_LOCAL,
            },
        )

    def test_exactly_one_candidate_is_selected(self):
        selected = [
            item
            for item in VECTOR_BACKEND_EVALUATIONS
            if item.decision is CandidateDecision.SELECTED
        ]
        self.assertEqual(len(selected), 1)
        self.assertEqual(
            selected[0].backend,
            VectorStorageBackend.QDRANT_LOCAL,
        )

    def test_selected_qdrant_mode_is_persistent_without_server(self):
        selected = selected_vector_backend_evaluation()

        self.assertEqual(
            SELECTED_VECTOR_BACKEND,
            VectorStorageBackend.QDRANT_LOCAL,
        )
        self.assertEqual(SELECTED_VECTOR_PACKAGE, "qdrant-client")
        self.assertEqual(SELECTED_VECTOR_PACKAGE_VERSION, "1.19.1")
        self.assertTrue(VECTOR_BACKEND_PERSISTED_LOCAL_MODE)
        self.assertFalse(VECTOR_BACKEND_EXTERNAL_SERVER_REQUIRED)
        self.assertEqual(VECTOR_BACKEND_SCOPE, "LOCAL_SINGLE_USER")
        self.assertTrue(selected.persisted_local_mode)
        self.assertFalse(selected.requires_external_server)

    def test_auto_install_is_disabled_for_every_candidate(self):
        self.assertFalse(VECTOR_BACKEND_AUTO_INSTALL_ALLOWED)
        self.assertTrue(
            all(
                not item.auto_install_allowed
                for item in VECTOR_BACKEND_EVALUATIONS
            )
        )

    def test_observed_windows_wheel_sizes_are_recorded(self):
        sizes = {
            item.backend: item.observed_wheel_bytes
            for item in VECTOR_BACKEND_EVALUATIONS
        }

        self.assertEqual(
            sizes[VectorStorageBackend.QDRANT_LOCAL],
            406533,
        )
        self.assertEqual(
            sizes[VectorStorageBackend.SQLITE_VEC],
            292804,
        )
        self.assertEqual(
            sizes[VectorStorageBackend.LANCEDB_LOCAL],
            83389723,
        )
        self.assertTrue(
            all(
                item.wheel_measurement_excludes_dependencies
                for item in VECTOR_BACKEND_EVALUATIONS
            )
        )

    def test_scores_cover_all_handoff_axes(self):
        for item in VECTOR_BACKEND_EVALUATIONS:
            for field_name in (
                "stability_score",
                "size_score",
                "performance_score",
                "installation_score",
                "backup_score",
                "portability_score",
            ):
                score = getattr(item, field_name)
                self.assertGreaterEqual(score, 1)
                self.assertLessEqual(score, 5)

    def test_invalid_score_is_rejected(self):
        with self.assertRaises(ValueError):
            VectorBackendEvaluation(
                backend=VectorStorageBackend.QDRANT_LOCAL,
                decision=CandidateDecision.REJECTED,
                stability_score=0,
                size_score=1,
                performance_score=1,
                installation_score=1,
                backup_score=1,
                portability_score=1,
                package_name="example",
                observed_version="1",
                observed_wheel_bytes=1,
                wheel_measurement_excludes_dependencies=True,
                persisted_local_mode=True,
                requires_external_server=False,
                auto_install_allowed=False,
                rationale="invalid score test",
            )


if __name__ == "__main__":
    unittest.main()
