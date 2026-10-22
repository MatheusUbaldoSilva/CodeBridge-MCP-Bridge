import hashlib
import unittest
from rag.runtime.incremental_preview_queue_handoff import prepare_preview_queue_handoff


class PreviewQueueHandoffTests(unittest.TestCase):
    def preview(self, *, intent="INDEX_NEW", state="ELIGIBLE_FOR_DURABLE_QUEUE"):
        return {
            "state": "EXPLICIT_SOURCE_PREVIEW_ONLY", "read_only": True,
            "queued": False, "safe_to_publish": False,
            "public_generation": "v1_delta_1ae1d01ea84f4e",
            "observed_commit": "a" * 40,
            "candidates": [{
                "path": "rag/runtime/example.py",
                "head": "a" * 40, "sha256": "b" * 64,
                "state": state, "intent": intent,
            }],
        }

    def test_new_source_intent_matches_queue_deterministic_job_id(self):
        result = prepare_preview_queue_handoff(
            self.preview(), approved_paths=("rag/runtime/example.py",),
        )
        self.assertEqual(result["state"], "ADVISORY_QUEUE_INTENTS_PREPARED")
        item = result["intents"][0]
        expected = hashlib.sha256(
            ("codebridge\0" + "rag/runtime/example.py" + "\0"
             + "a" * 40 + "\0" + "b" * 64).encode()
        ).hexdigest()
        self.assertEqual(item["prospective_job_id"], expected)
        self.assertEqual(item["purpose"], "INDEX_NEW")
        self.assertFalse(result["queued"])
        self.assertTrue(result["must_revalidate_at_enqueue"])

    def test_stale_existing_source_allowed_as_review_intent(self):
        result = prepare_preview_queue_handoff(
            self.preview(intent="REINDEX_CHANGED"),
            approved_paths=("rag/runtime/example.py",),
        )
        self.assertEqual(result["intents"][0]["purpose"], "REINDEX_CHANGED")
        self.assertFalse(result["safe_to_publish"])

    def test_unapproved_or_unstable_source_blocks(self):
        report = prepare_preview_queue_handoff(
            self.preview(state="AWAITING_STABLE_COMMIT"),
            approved_paths=("rag/runtime/example.py",),
        )
        self.assertEqual(report["state"], "HANDOFF_BLOCKED")
        report = prepare_preview_queue_handoff(
            self.preview(), approved_paths=("rag/runtime/unapproved.py",),
        )
        self.assertEqual(report["reason"], "PREVIEW_SCOPE_MISMATCH")

    def test_forged_head_or_sha_blocks(self):
        preview = self.preview()
        preview["candidates"][0]["head"] = "c" * 40
        self.assertEqual(
            prepare_preview_queue_handoff(
                preview, approved_paths=("rag/runtime/example.py",),
            )["state"], "HANDOFF_BLOCKED",
        )
        preview = self.preview()
        preview["candidates"][0]["sha256"] = "bad"
        self.assertEqual(
            prepare_preview_queue_handoff(
                preview, approved_paths=("rag/runtime/example.py",),
            )["state"], "HANDOFF_BLOCKED",
        )

    def test_path_traversal_cannot_enter_handoff(self):
        candidate = self.preview()
        candidate["candidates"][0]["path"] = "../sensitive.py"
        value = prepare_preview_queue_handoff(
            candidate, approved_paths=("../sensitive.py",),
        )
        self.assertEqual(value["reason"], "INVALID_EXPLICIT_APPROVALS")

    def test_invalid_public_generation_denies(self):
        candidate = self.preview()
        candidate["public_generation"] = "unknown"
        value = prepare_preview_queue_handoff(
            candidate, approved_paths=("rag/runtime/example.py",),
        )
        self.assertEqual(value["reason"], "PUBLIC_GENERATION_UNVERIFIED")

    def test_no_explicit_operator_scope_never_produces_intents(self):
        self.assertEqual(
            prepare_preview_queue_handoff(self.preview(), approved_paths=())["intents"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
