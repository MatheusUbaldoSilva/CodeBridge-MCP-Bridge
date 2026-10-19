"""Crash after pointer swap and startup recovery, test-only."""
import multiprocessing as mp
import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_validate import fixture
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_transition_journal import (
    _atomic_json, prepare_transition, recover_pending_transition,
    inspect_pending_transition, TransitionRecoveryError, JOURNAL,
)


def crash_after_pointer_swap(root):
    _atomic_json(Path(root) / "active-generation.json", {
        "schema_version": 1, "generation": "two",
    })
    os._exit(41)


class TransitionJournalTests(unittest.TestCase):
    def setup_generations(self, root):
        for name in ("one", "two"):
            folder = root / "generations" / name
            folder.mkdir(parents=True)
            fixture(folder)
        activate_test_generation(root, "one")

    def test_crash_after_pointer_swap_recovers_previous(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "codebridge-rag-generation-test"
            root.mkdir()
            self.setup_generations(root)
            prepare_transition(root, "one", "two")
            ctx = mp.get_context("spawn")
            worker = ctx.Process(target=crash_after_pointer_swap, args=(root,))
            worker.start()
            worker.join(timeout=8)
            if worker.is_alive():
                worker.terminate()
                worker.join()
                self.fail("worker did not exit")
            self.assertEqual(worker.exitcode, 41)
            self.assertEqual(resolve_generation(root).generation, "two")
            self.assertEqual(inspect_pending_transition(root)["state"], "PENDING_TRANSITION")
            result = recover_pending_transition(root)
            self.assertEqual(result["state"], "RECOVERED_PREVIOUS")
            self.assertEqual(resolve_generation(root).generation, "one")
            self.assertFalse((root / JOURNAL).exists())
            self.assertTrue((root / "generations" / "two").exists())

    def test_crash_before_pointer_swap_retains_previous(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "codebridge-rag-generation-test"
            root.mkdir()
            self.setup_generations(root)
            prepare_transition(root, "one", "two")
            self.assertEqual(recover_pending_transition(root)["generation"], "one")
            self.assertEqual(resolve_generation(root).generation, "one")

    def test_corrupt_journal_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "codebridge-rag-generation-test"
            root.mkdir()
            self.setup_generations(root)
            (root / JOURNAL).write_text("{garbage")
            with self.assertRaises(TransitionRecoveryError):
                recover_pending_transition(root)
            self.assertEqual(resolve_generation(root).generation, "one")


if __name__ == "__main__":
    unittest.main()


class ProductionPointerRecoveryTests(unittest.TestCase):
    """Exercise production control-file recovery without any live RAG mutation."""

    def test_pre_and_post_pointer_recovery_retains_candidate(self):
        from contextlib import nullcontext
        from unittest.mock import patch
        import rag.runtime.production_generation_transition as prod

        candidate = "v1_delta_e4b1a435382f48"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "rag"
            (root / "generations" / candidate).mkdir(parents=True)
            with patch.object(prod, "_root", return_value=root), patch.object(
                prod, "production_generation_lock", side_effect=lambda **_: nullcontext()
            ):
                self.assertEqual(prod.inspect_transition()["active"], "legacy")
                journal = {
                    "schema_version": 1, "state": "PREPARED",
                    "previous": "legacy", "candidate": candidate,
                }
                prod._atomic_json(root / prod.JOURNAL_NAME, journal)
                self.assertEqual(prod.inspect_transition()["state"], "RECOVERY_REQUIRED")
                self.assertEqual(
                    prod.rollback_pending_to_legacy(expected_candidate=candidate)["state"],
                    "RECOVERED_LEGACY"
                )
                self.assertFalse((root / prod.POINTER_NAME).exists())
                self.assertFalse((root / prod.JOURNAL_NAME).exists())

                prod._atomic_json(root / prod.JOURNAL_NAME, journal)
                prod._atomic_json(root / prod.POINTER_NAME, {
                    "schema_version": 1, "generation": candidate,
                })
                self.assertEqual(prod.inspect_transition()["active"], candidate)
                done = prod.rollback_pending_to_legacy(expected_candidate=candidate)
                self.assertEqual(done["state"], "RECOVERED_LEGACY")
                self.assertFalse((root / prod.POINTER_NAME).exists())
                self.assertFalse((root / prod.JOURNAL_NAME).exists())
                self.assertTrue(
                    (root / ("recovered-pointer-" + candidate + ".json")).is_file()
                )
                self.assertTrue((root / "generations" / candidate).is_dir())

    def test_corrupt_production_journal_blocks_recovery(self):
        from contextlib import nullcontext
        from unittest.mock import patch
        import rag.runtime.production_generation_transition as prod

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "rag"
            root.mkdir()
            (root / prod.JOURNAL_NAME).write_text(
                "{broken", encoding="utf-8"
            )
            with patch.object(prod, "_root", return_value=root), patch.object(
                prod, "production_generation_lock", side_effect=lambda **_: nullcontext()
            ):
                with self.assertRaises((ValueError, prod.GenerationTransitionBlocked)):
                    prod.rollback_pending_to_legacy(
                        expected_candidate="v1_delta_e4b1a435382f48"
                    )
                self.assertTrue((root / prod.JOURNAL_NAME).exists())



class ProductionCompletedRollbackTests(unittest.TestCase):
    def test_approved_completed_rollback_retains_version_and_archives_pointer(self):
        from contextlib import nullcontext
        from unittest.mock import patch
        import rag.runtime.production_generation_transition as prod

        candidate = "v1_delta_e4b1a435382f48"
        baseline = "v1_base_6142ab6e3b534f"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "rag"
            (root / "generations" / candidate).mkdir(parents=True)
            prod._atomic_json(root / prod.POINTER_NAME, {
                "schema_version": 1, "generation": candidate,
            })
            with patch.object(prod, "_root", return_value=root), patch.object(
                prod, "production_generation_lock", side_effect=lambda **_: nullcontext()
            ), patch(
                "rag.runtime.production_cutover_gate._verify_versioned",
                return_value={"validation": {"documents": 210, "chunks": 8761}},
            ), patch(
                "rag.runtime.live_integrity.inspect_live_index",
                return_value={"documents": 210, "chunks": 8761},
            ):
                with self.assertRaises(prod.GenerationTransitionBlocked):
                    prod.revert_active_to_legacy(
                        baseline=baseline, expected_candidate=candidate,
                        operator_authorization="NOT_APPROVED",
                    )
                self.assertTrue((root / prod.POINTER_NAME).exists())
                result = prod.revert_active_to_legacy(
                    baseline=baseline, expected_candidate=candidate,
                    operator_authorization="CODEBRIDGE_RAG_V1_ROLLBACK:" + candidate,
                )
                self.assertEqual(result["state"], "RECOVERED_LEGACY")
                self.assertFalse((root / prod.POINTER_NAME).exists())
                self.assertFalse((root / prod.JOURNAL_NAME).exists())
                self.assertTrue(
                    (root / ("recovered-pointer-" + candidate + ".json")).exists()
                )
                self.assertTrue((root / "generations" / candidate).is_dir())


class ProductionPointerAtomicCommitTests(unittest.TestCase):
    def test_publish_and_revert_pointer_in_isolated_controls(self):
        from contextlib import nullcontext
        from unittest.mock import patch
        import rag.runtime.production_generation_transition as prod
        candidate = "v1_delta_e4b1a435382f48"
        baseline = "v1_base_6142ab6e3b534f"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "rag"
            (root / "generations" / candidate).mkdir(parents=True)
            with patch.object(prod,"_root",return_value=root), patch.object(
                prod,"production_generation_lock",side_effect=lambda **kw:nullcontext()
            ),patch("rag.runtime.production_cutover_gate.assess_real_cutover",return_value={
                "state":"READY","safe_to_activate":True,"blockers":[],
                "verified":{"candidate":{"validation":{"documents":211}}}
            }),patch("rag.runtime.incremental_bundle_validate.validate_incremental_bundle",
                return_value={"documents":211}):
                done=prod.publish_validated_generation(
                    baseline=baseline,candidate=candidate,
                    operator_authorization="CODEBRIDGE_RAG_V1_ACTIVATE:"+candidate,
                    public_reader_attestation={"generation_lock_enabled":True,
                                              "mcp_restart_confirmed":True})
                self.assertEqual(done["state"],"POINTER_ACTIVATED_PENDING_PUBLIC_QUERY_PROOF")
                self.assertEqual(prod.inspect_transition()["active"],candidate)
                self.assertFalse((root/prod.JOURNAL_NAME).exists())
            with patch.object(prod,"_root",return_value=root),patch.object(
                prod,"production_generation_lock",side_effect=lambda **kw:nullcontext()
            ),patch("rag.runtime.production_cutover_gate._verify_versioned",
              return_value={"validation":{"documents":210,"chunks":8761}}),patch(
                "rag.runtime.live_integrity.inspect_live_index",
                return_value={"documents":210,"chunks":8761}):
                result=prod.revert_active_to_legacy(
                    baseline=baseline,expected_candidate=candidate,
                    operator_authorization="CODEBRIDGE_RAG_V1_ROLLBACK:"+candidate)
                self.assertEqual(result["state"],"RECOVERED_LEGACY")
                self.assertEqual(prod.inspect_transition()["active"],"legacy")
                self.assertFalse((root/prod.JOURNAL_NAME).exists())
                self.assertTrue((root/"generations"/candidate).is_dir())

    def test_interruption_before_pointer_swap_leaves_recoverable_journal(self):
        from contextlib import nullcontext
        from unittest.mock import patch
        import rag.runtime.production_generation_transition as prod
        candidate = "v1_delta_e4b1a435382f48"
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"rag"
            (root/"generations"/candidate).mkdir(parents=True)
            real_atomic=prod._atomic_json
            def injected(path,payload):
                if path.name==prod.POINTER_NAME:
                    raise OSError("injected interruption before swap")
                return real_atomic(path,payload)
            with patch.object(prod,"_root",return_value=root), patch.object(
                prod,"production_generation_lock",side_effect=lambda **kw:nullcontext()
            ), patch.object(prod,"_atomic_json",side_effect=injected),patch(
                "rag.runtime.production_cutover_gate.assess_real_cutover",return_value={
                    "state":"READY","safe_to_activate":True,"blockers":[],
                    "verified":{"candidate":{"validation":{"documents":211}}}
                }):
                with self.assertRaises(OSError):
                    prod.publish_validated_generation(
                        baseline="v1_base_6142ab6e3b534f",candidate=candidate,
                        operator_authorization="CODEBRIDGE_RAG_V1_ACTIVATE:"+candidate,
                        public_reader_attestation={"generation_lock_enabled":True,
                                                   "mcp_restart_confirmed":True})
                self.assertTrue((root/prod.JOURNAL_NAME).exists())
                self.assertFalse((root/prod.POINTER_NAME).exists())
            with patch.object(prod,"_root",return_value=root),patch.object(
                prod,"production_generation_lock",side_effect=lambda **kw:nullcontext()
            ):
                self.assertEqual(prod.rollback_pending_to_legacy(
                    expected_candidate=candidate)["state"],"RECOVERED_LEGACY")
                self.assertFalse((root/prod.JOURNAL_NAME).exists())
