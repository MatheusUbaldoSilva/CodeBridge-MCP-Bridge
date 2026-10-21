"""Post-pointer failure injection: isolated control files only."""
from contextlib import nullcontext
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag.runtime import production_generation_transition as writer
from rag.runtime import production_generation_read as reader

CANDIDATE = "v1_delta_a1b2c3d4"
BASELINE = "v1_base_a1b2c3d4"
OPTIONS = {
    "baseline": BASELINE, "candidate": CANDIDATE,
    "operator_authorization": "CODEBRIDGE_RAG_V1_ACTIVATE:" + CANDIDATE,
    "public_reader_attestation": {
        "generation_lock_enabled": True, "mcp_restart_confirmed": True,
    },
}


class IsolatedPostPointerFaultTests(unittest.TestCase):
    def test_wrong_rollback_candidate_keeps_evidence_and_state(self):
        with tempfile.TemporaryDirectory(prefix="codebridge-p3-wrong-target-") as tmp:
            root = Path(tmp) / "CodeBridge" / "rag"
            (root / "generations" / CANDIDATE).mkdir(parents=True)
            writer._atomic_json(root / writer.JOURNAL_NAME, {
                "schema_version": 1, "state": "PREPARED",
                "previous": "legacy", "candidate": CANDIDATE})
            writer._atomic_json(root / writer.POINTER_NAME, {
                "schema_version": 1, "generation": CANDIDATE})
            journal_before = (root / writer.JOURNAL_NAME).read_bytes()
            pointer_before = (root / writer.POINTER_NAME).read_bytes()
            with patch.object(writer, "_root", return_value=root), patch.object(
                writer, "production_generation_lock", side_effect=lambda **_: nullcontext()
            ):
                with self.assertRaisesRegex(writer.GenerationTransitionBlocked, "no matching pending journal"):
                    writer.rollback_pending_to_legacy(
                        expected_candidate="v1_delta_ffffffff")
            self.assertEqual((root / writer.JOURNAL_NAME).read_bytes(), journal_before)
            self.assertEqual((root / writer.POINTER_NAME).read_bytes(), pointer_before)

    def test_unexpected_pointer_blocks_pending_rollback_preserving_evidence(self):
        with tempfile.TemporaryDirectory(prefix="codebridge-p3-pointer-conflict-") as tmp:
            root=Path(tmp)/"CodeBridge"/"rag"
            (root/"generations"/CANDIDATE).mkdir(parents=True)
            (root/"generations"/"v1_delta_unknown123").mkdir(parents=True)
            writer._atomic_json(root/writer.JOURNAL_NAME, {
                "schema_version": 1, "state": "PREPARED",
                "previous": "legacy", "candidate": CANDIDATE})
            writer._atomic_json(root/writer.POINTER_NAME, {
                "schema_version": 1, "generation": "v1_delta_unknown123"})
            journal_before=(root/writer.JOURNAL_NAME).read_bytes()
            pointer_before=(root/writer.POINTER_NAME).read_bytes()
            with patch.object(writer,"_root",return_value=root), patch.object(
                writer,"production_generation_lock",side_effect=lambda **_:nullcontext()
            ):
                with self.assertRaisesRegex(writer.GenerationTransitionBlocked,"pointer conflicts"):
                    writer.rollback_pending_to_legacy(expected_candidate=CANDIDATE)
            self.assertEqual((root/writer.JOURNAL_NAME).read_bytes(),journal_before)
            self.assertEqual((root/writer.POINTER_NAME).read_bytes(),pointer_before)

    def test_preserved_pointer_collision_blocks_rollback_without_mutation(self):
        with tempfile.TemporaryDirectory(prefix="codebridge-p3-rollback-collision-") as tmp:
            root=Path(tmp)/"CodeBridge"/"rag"
            (root/"generations"/CANDIDATE).mkdir(parents=True)
            writer._atomic_json(root/writer.JOURNAL_NAME, {
                "schema_version":1, "state":"PREPARED",
                "previous":"legacy", "candidate":CANDIDATE})
            writer._atomic_json(root/writer.POINTER_NAME, {
                "schema_version":1, "generation":CANDIDATE})
            preserved=root/("recovered-pointer-"+CANDIDATE+".json")
            preserved.write_text("prior-record",encoding="utf-8")
            pointer_before=(root/writer.POINTER_NAME).read_bytes()
            journal_before=(root/writer.JOURNAL_NAME).read_bytes()
            with patch.object(writer,"_root",return_value=root), patch.object(
                writer,"production_generation_lock",side_effect=lambda **_:nullcontext()
            ):
                with self.assertRaisesRegex(writer.GenerationTransitionBlocked,"artifact collision"):
                    writer.rollback_pending_to_legacy(expected_candidate=CANDIDATE)
            self.assertEqual(preserved.read_text(encoding="utf-8"),"prior-record")
            self.assertEqual((root/writer.JOURNAL_NAME).read_bytes(),journal_before)
            self.assertEqual((root/writer.POINTER_NAME).read_bytes(),pointer_before)

    def test_unapproved_activation_does_not_create_control_files(self):
        with tempfile.TemporaryDirectory(prefix="codebridge-p3-no-approval-") as tmp:
            root=Path(tmp)/"CodeBridge"/"rag"
            (root/"generations"/CANDIDATE).mkdir(parents=True)
            with patch.object(writer,"_root",return_value=root):
                with self.assertRaisesRegex(writer.GenerationTransitionBlocked,
                                            "explicit generation-specific approval"):
                    writer.publish_validated_generation(
                        **{**OPTIONS,"operator_authorization":"NOT_AUTHORIZED"})
            self.assertFalse((root/writer.JOURNAL_NAME).exists())
            self.assertFalse((root/writer.POINTER_NAME).exists())

    def test_failure_after_pointer_swap_requires_explicit_rollback(self):
        with tempfile.TemporaryDirectory(prefix="codebridge-p3-post-pointer-") as tmp:
            root = Path(tmp) / "CodeBridge" / "rag"
            bundle = root / "generations" / CANDIDATE
            bundle.mkdir(parents=True)
            (bundle / "rag_index.sqlite3").write_bytes(b"isolated-index")
            (bundle / "rag-index-manifest.json").write_text("{}", encoding="utf-8")
            (bundle / "qdrant").mkdir()
            (root / "rag_index.sqlite3").write_bytes(b"legacy-untouched")
            with patch.object(writer, "_root", return_value=root), patch.object(
                writer, "production_generation_lock", side_effect=lambda **_: nullcontext()
            ), patch(
                "rag.runtime.production_cutover_gate.assess_real_cutover",
                return_value={
                    "state": "READY", "safe_to_activate": True, "blockers": [],
                    "verified": {"candidate": {"validation": {"documents": 211}}},
                },
            ), patch.object(
                writer, "_verify_target_after_pointer",
                side_effect=OSError("injected verification failure AFTER pointer"),
            ):
                with self.assertRaisesRegex(OSError, "AFTER pointer"):
                    writer.publish_validated_generation(**OPTIONS)
            self.assertTrue((root / writer.JOURNAL_NAME).exists())
            self.assertTrue((root / writer.POINTER_NAME).exists())
            with patch.object(reader, "production_generation_lock", side_effect=lambda **_: nullcontext()), patch.object(
                reader, "resolve_rag_sqlite_path", return_value=root / "rag_index.sqlite3"
            ):
                with self.assertRaisesRegex(RuntimeError, "recovery required"):
                    with reader.production_generation_read():
                        pass
            with patch.object(writer, "_root", return_value=root), patch.object(
                writer, "production_generation_lock", side_effect=lambda **_: nullcontext()
            ):
                result = writer.rollback_pending_to_legacy(expected_candidate=CANDIDATE)
            self.assertEqual(result["state"], "RECOVERED_LEGACY")
            self.assertFalse((root / writer.POINTER_NAME).exists())
            self.assertFalse((root / writer.JOURNAL_NAME).exists())
            self.assertTrue((root / ("recovered-pointer-" + CANDIDATE + ".json")).is_file())
            self.assertTrue((bundle / "rag_index.sqlite3").exists())
            self.assertEqual((root / "rag_index.sqlite3").read_bytes(), b"legacy-untouched")
