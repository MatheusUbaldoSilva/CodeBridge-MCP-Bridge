"""Pre-pointer failure and recovery, test-only control files."""
from contextlib import nullcontext
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rag.runtime import production_generation_transition as writer
from rag.runtime import production_generation_read as reader
from test_p3_post_pointer_recovery_isolated import OPTIONS, CANDIDATE


class PrePointerFailClosedTests(unittest.TestCase):
    def test_failure_to_write_journal_does_not_create_pointer(self):
        with tempfile.TemporaryDirectory(prefix="codebridge-p3-nojournal-") as tmp:
            root=Path(tmp)/"CodeBridge"/"rag"
            folder=root/"generations"/CANDIDATE
            folder.mkdir(parents=True)
            (root/"rag_index.sqlite3").write_bytes(b"legacy-unmodified")
            with patch.object(writer,"_root",return_value=root), patch.object(
                writer,"production_generation_lock",side_effect=lambda **_:nullcontext()
            ), patch("rag.runtime.production_cutover_gate.assess_real_cutover",return_value={
                "state":"READY","safe_to_activate":True,"blockers":[],
                "verified":{"candidate":{"validation":{"documents":211}}}
            }), patch.object(writer,"_atomic_json",side_effect=OSError("injected journal IO failure")):
                with self.assertRaisesRegex(OSError,"journal IO failure"):
                    writer.publish_validated_generation(**OPTIONS)
            self.assertFalse((root/writer.JOURNAL_NAME).exists())
            self.assertFalse((root/writer.POINTER_NAME).exists())
            self.assertEqual((root/"rag_index.sqlite3").read_bytes(),b"legacy-unmodified")

    def test_journal_write_then_pointer_failure_preserves_legacy(self):
        with tempfile.TemporaryDirectory(prefix="codebridge-p3-prepointer-") as tmp:
            root=Path(tmp)/"CodeBridge"/"rag"
            folder=root/"generations"/CANDIDATE
            folder.mkdir(parents=True)
            (folder/"rag_index.sqlite3").write_bytes(b"candidate")
            (folder/"rag-index-manifest.json").write_text("{}",encoding="utf-8")
            (folder/"qdrant").mkdir()
            (root/"rag_index.sqlite3").write_bytes(b"original-legacy")
            original=writer._atomic_json
            def fault_on_pointer(path,payload):
                if Path(path).name==writer.POINTER_NAME:
                    raise OSError("injected interruption BEFORE pointer")
                return original(path,payload)
            with patch.object(writer,"_root",return_value=root), patch.object(
                writer,"production_generation_lock",side_effect=lambda **_:nullcontext()
            ), patch("rag.runtime.production_cutover_gate.assess_real_cutover",return_value={
                "state":"READY","safe_to_activate":True,"blockers":[],
                "verified":{"candidate":{"validation":{"documents":211}}}
            }), patch.object(writer,"_atomic_json",side_effect=fault_on_pointer):
                with self.assertRaisesRegex(OSError,"BEFORE pointer"):
                    writer.publish_validated_generation(**OPTIONS)
            self.assertTrue((root/writer.JOURNAL_NAME).is_file())
            self.assertFalse((root/writer.POINTER_NAME).exists())
            with patch.object(reader,"production_generation_lock",side_effect=lambda **_:nullcontext()), patch.object(
                reader,"resolve_rag_sqlite_path",return_value=root/"rag_index.sqlite3"
            ):
                with self.assertRaisesRegex(RuntimeError,"recovery required"):
                    with reader.production_generation_read():pass
            with patch.object(writer,"_root",return_value=root), patch.object(
                writer,"production_generation_lock",side_effect=lambda **_:nullcontext()
            ):
                report=writer.rollback_pending_to_legacy(expected_candidate=CANDIDATE)
            self.assertEqual(report["state"],"RECOVERED_LEGACY")
            self.assertFalse((root/writer.JOURNAL_NAME).exists())
            self.assertEqual((root/"rag_index.sqlite3").read_bytes(),b"original-legacy")
            self.assertTrue((folder/"rag_index.sqlite3").exists())
