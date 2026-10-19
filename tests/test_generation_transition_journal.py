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
            }),patch("rag.runtime.production_generation_transition._verify_target_after_pointer",
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


class ProductionWindowsRealLockCycleTests(unittest.TestCase):
    """Real Win32 LockFileEx on an isolated temporary CodeBridge root.

    Only gate/data verification are mocked. The lock and journaled pointer
    filesystem operations run unchanged. The real RAG root is never opened.
    """
    def test_reader_blocks_atomic_writer_until_release_and_rollback(self):
        from unittest.mock import patch
        from rag.runtime.production_generation_transition import (
            publish_validated_generation, revert_active_to_legacy,
            inspect_transition,
        )
        from rag.runtime.production_generation_lock import (
            production_generation_lock, ProductionGenerationBusy,
        )

        candidate = "v1_delta_e4b1a435382f48"
        baseline = "v1_base_6142ab6e3b534f"
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "CodeBridge" / "rag"
            (state / "generations" / candidate).mkdir(parents=True)
            fake_db = state / "rag_index.sqlite3"
            with patch(
                "rag.runtime.production_generation_transition._root",
                return_value=state,
            ), patch(
                "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                return_value=fake_db,
            ), patch(
                "rag.runtime.production_cutover_gate.assess_real_cutover",
                return_value={
                    "state": "READY", "safe_to_activate": True,
                    "blockers": [],
                    "verified": {"candidate": {"validation": {"documents": 211}}},
                },
            ), patch(
                "rag.runtime.production_generation_transition._verify_target_after_pointer",
                return_value={"documents": 211},
            ):
                options = {
                    "baseline": baseline,
                    "candidate": candidate,
                    "operator_authorization": "CODEBRIDGE_RAG_V1_ACTIVATE:" + candidate,
                    "public_reader_attestation": {
                        "generation_lock_enabled": True,
                        "mcp_restart_confirmed": True,
                    },
                }
                with production_generation_lock(exclusive=False):
                    with self.assertRaises(ProductionGenerationBusy):
                        publish_validated_generation(**options)
                    self.assertFalse((state / "active-generation.json").exists())
                published = publish_validated_generation(**options)
                self.assertEqual(
                    published["state"], "POINTER_ACTIVATED_PENDING_PUBLIC_QUERY_PROOF",
                )
                self.assertEqual(inspect_transition()["active"], candidate)
                self.assertFalse(
                    (state / "production-generation-transition.json").exists()
                )

            with patch(
                "rag.runtime.production_generation_transition._root",
                return_value=state,
            ), patch(
                "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                return_value=fake_db,
            ), patch(
                "rag.runtime.production_cutover_gate._verify_versioned",
                return_value={"validation": {"documents": 210, "chunks": 8761}},
            ), patch(
                "rag.runtime.live_integrity.inspect_live_index",
                return_value={"documents": 210, "chunks": 8761},
            ):
                result = revert_active_to_legacy(
                    baseline=baseline,
                    expected_candidate=candidate,
                    operator_authorization="CODEBRIDGE_RAG_V1_ROLLBACK:" + candidate,
                )
                self.assertEqual(result["state"], "RECOVERED_LEGACY")
                self.assertFalse((state / "active-generation.json").exists())
                self.assertFalse(
                    (state / "production-generation-transition.json").exists()
                )
                self.assertTrue((state / "generations" / candidate).is_dir())
                self.assertTrue((state / (
                    "recovered-pointer-" + candidate + ".json"
                )).is_file())
class ProductionSemanticLockChannelTests(unittest.TestCase):
    def test_real_win32_semantic_lock_is_separate_from_generation_lock(self):
        from unittest.mock import patch
        from rag.runtime.production_generation_lock import (
            ProductionGenerationBusy, production_generation_lock,
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "CodeBridge" / "rag"
            root.mkdir(parents=True)
            with patch(
                "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                return_value=root / "rag_index.sqlite3",
            ):
                with production_generation_lock(exclusive=False):
                    # The semantic worker must run under a shared generation
                    # reader without deadlocking with its own separate lock.
                    with production_generation_lock(exclusive=True, channel="semantic"):
                        with self.assertRaises(ProductionGenerationBusy):
                            with production_generation_lock(
                                exclusive=True, channel="semantic"
                            ):
                                self.fail("a second semantic worker entered")
                        with self.assertRaises(ProductionGenerationBusy):
                            with production_generation_lock(exclusive=True):
                                self.fail("generation writer entered under reader")
                    # Reader is still present after the semantic worker exits.
                    with self.assertRaises(ProductionGenerationBusy):
                        with production_generation_lock(exclusive=True):
                            self.fail("generation writer acquired early")
                with production_generation_lock(exclusive=True):
                    pass
                with production_generation_lock(exclusive=True, channel="semantic"):
                    pass



class ProductionPendingJournalReaderRecoveryTests(unittest.TestCase):
    def test_real_writer_verification_crash_keeps_journal_then_reader_recovers(self):
        from unittest.mock import patch
        from rag.runtime.production_generation_transition import (
            publish_validated_generation, rollback_pending_to_legacy,
            JOURNAL_NAME, POINTER_NAME,
        )
        from rag.runtime.production_generation_read import production_generation_read

        candidate = "v1_delta_e4b1a435382f48"
        baseline = "v1_base_6142ab6e3b534f"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "CodeBridge" / "rag"
            (root / "generations" / candidate).mkdir(parents=True)
            database = root / "rag_index.sqlite3"
            database.write_bytes(b"original-ready-index")
            manifest = root / "rag-index-manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            qdrant = root / "qdrant"
            qdrant.mkdir()
            with patch(
                "rag.runtime.production_generation_transition._root",
                return_value=root,
            ), patch(
                "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                return_value=database,
            ), patch(
                "rag.runtime.production_generation_read.resolve_rag_sqlite_path",
                return_value=database,
            ), patch(
                "rag.runtime.production_generation_read.resolve_rag_manifest_path",
                return_value=manifest,
            ), patch(
                "rag.runtime.production_generation_read.resolve_qdrant_local_path",
                return_value=qdrant,
            ), patch(
                "rag.runtime.production_cutover_gate.assess_real_cutover",
                return_value={
                    "state": "READY", "safe_to_activate": True, "blockers": [],
                    "verified": {"candidate": {"validation": {"documents": 211}}},
                },
            ), patch(
                "rag.runtime.production_generation_transition._verify_target_after_pointer",
                side_effect=RuntimeError("injected validation failure after swap"),
            ):
                with self.assertRaisesRegex(RuntimeError, "injected validation"):
                    publish_validated_generation(
                        baseline=baseline,
                        candidate=candidate,
                        operator_authorization="CODEBRIDGE_RAG_V1_ACTIVATE:" + candidate,
                        public_reader_attestation={
                            "generation_lock_enabled": True,
                            "mcp_restart_confirmed": True,
                        },
                    )
                self.assertTrue((root / JOURNAL_NAME).is_file())
                self.assertTrue((root / POINTER_NAME).is_file())
                with self.assertRaisesRegex(RuntimeError, "recovery required"):
                    with production_generation_read():
                        self.fail("partial published generation exposed")
                done = rollback_pending_to_legacy(expected_candidate=candidate)
                self.assertEqual(done["state"], "RECOVERED_LEGACY")
                with production_generation_read() as selected:
                    self.assertEqual(selected.generation, "legacy")
                self.assertEqual(database.read_bytes(), b"original-ready-index")
                self.assertFalse((root / JOURNAL_NAME).exists())
                self.assertFalse((root / POINTER_NAME).exists())
                self.assertTrue((root / "generations" / candidate).is_dir())
                self.assertTrue(
                    (root / ("recovered-pointer-" + candidate + ".json")).is_file()
                )

    def test_real_lock_reader_fails_closed_during_journal_then_recovers(self):
        from unittest.mock import patch
        from rag.runtime.production_generation_read import production_generation_read
        from rag.runtime.production_generation_transition import (
            _atomic_json, rollback_pending_to_legacy, JOURNAL_NAME, POINTER_NAME,
        )

        candidate = "v1_delta_e4b1a435382f48"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "CodeBridge" / "rag"
            root.mkdir(parents=True)
            legacy_db = root / "rag_index.sqlite3"
            legacy_db.write_bytes(b"legacy-database-unchanged")
            manifest = root / "rag-index-manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            qdrant = root / "qdrant"
            qdrant.mkdir()
            immutable = root / "generations" / candidate
            immutable.mkdir(parents=True)
            for source in ("rag_index.sqlite3", "rag-index-manifest.json"):
                (immutable / source).write_bytes(b"versioned-data")
            (immutable / "qdrant").mkdir()
            from rag.runtime.production_generation_lock import (
                production_generation_lock,
            )
            with patch(
                "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                return_value=legacy_db,
            ), patch(
                "rag.runtime.production_generation_read.resolve_rag_sqlite_path",
                return_value=legacy_db,
            ), patch(
                "rag.runtime.production_generation_read.resolve_rag_manifest_path",
                return_value=manifest,
            ), patch(
                "rag.runtime.production_generation_read.resolve_qdrant_local_path",
                return_value=qdrant,
            ), patch(
                "rag.runtime.production_generation_transition._root",
                return_value=root,
            ):
                with production_generation_read() as pinned:
                    self.assertEqual(pinned.generation, "legacy")
                    self.assertEqual(pinned.sqlite, legacy_db.resolve())

                with production_generation_lock(exclusive=True):
                    _atomic_json(root / JOURNAL_NAME, {
                        "schema_version": 1, "state": "PREPARED",
                        "previous": "legacy", "candidate": candidate,
                    })
                    _atomic_json(root / POINTER_NAME, {
                        "schema_version": 1, "generation": candidate,
                    })
                with self.assertRaisesRegex(RuntimeError, "recovery required"):
                    with production_generation_read():
                        self.fail("reader entered during pending transition")
                self.assertEqual(legacy_db.read_bytes(), b"legacy-database-unchanged")
                result = rollback_pending_to_legacy(expected_candidate=candidate)
                self.assertEqual(result["state"], "RECOVERED_LEGACY")
                with production_generation_read() as pinned:
                    self.assertEqual(pinned.generation, "legacy")
                self.assertFalse((root / JOURNAL_NAME).exists())
                self.assertFalse((root / POINTER_NAME).exists())
                self.assertTrue((root / "generations" / candidate).exists())
                self.assertEqual(legacy_db.read_bytes(), b"legacy-database-unchanged")


class ProductionCompletedRollbackCrashTests(unittest.TestCase):
    """Simulate failures around rollback of an already activated generation."""

    def _run_case(self, interrupted_at: str):
        import os
        from unittest.mock import patch
        from rag.runtime.production_generation_read import production_generation_read
        import rag.runtime.production_generation_transition as transaction

        baseline = "v1_base_6142ab6e3b534f"
        candidate = "v1_delta_e4b1a435382f48"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "CodeBridge" / "rag"
            (root / "generations" / candidate).mkdir(parents=True)
            legacy_sqlite = root / "rag_index.sqlite3"
            legacy_sqlite.write_bytes(b"original-RAG-index")
            manifest = root / "rag-index-manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            qdrant = root / "qdrant"
            qdrant.mkdir()
            transaction._atomic_json(
                root / transaction.POINTER_NAME,
                {"schema_version": 1, "generation": candidate},
            )
            with patch.object(transaction, "_root", return_value=root), patch(
                "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                return_value=legacy_sqlite,
            ), patch(
                "rag.runtime.production_generation_read.resolve_rag_sqlite_path",
                return_value=legacy_sqlite,
            ), patch(
                "rag.runtime.production_generation_read.resolve_rag_manifest_path",
                return_value=manifest,
            ), patch(
                "rag.runtime.production_generation_read.resolve_qdrant_local_path",
                return_value=qdrant,
            ), patch(
                "rag.runtime.production_cutover_gate._verify_versioned",
                return_value={"validation": {"documents": 210, "chunks": 8761}},
            ), patch(
                "rag.runtime.live_integrity.inspect_live_index",
                return_value={"documents": 210, "chunks": 8761},
            ):
                real_replace = os.replace
                real_unlink = Path.unlink

                def crash_replace(source, target):
                    if (Path(source).name == transaction.POINTER_NAME
                            and Path(target).name.startswith("recovered-pointer-")):
                        raise OSError("injected failure before rollback rename")
                    return real_replace(source, target)

                def crash_unlink(path, *args, **kwargs):
                    if Path(path).name == transaction.JOURNAL_NAME:
                        raise OSError("injected failure after rollback rename")
                    return real_unlink(path, *args, **kwargs)

                fail_context = (
                    patch.object(transaction.os, "replace", side_effect=crash_replace)
                    if interrupted_at == "before_archive" else
                    patch.object(Path, "unlink", autospec=True,
                                 side_effect=crash_unlink)
                )
                with fail_context:
                    with self.assertRaisesRegex(OSError, "injected failure"):
                        transaction.revert_active_to_legacy(
                            baseline=baseline, expected_candidate=candidate,
                            operator_authorization=(
                                "CODEBRIDGE_RAG_V1_ROLLBACK:" + candidate
                            ),
                        )

                self.assertTrue((root / transaction.JOURNAL_NAME).is_file())
                with self.assertRaisesRegex(RuntimeError, "recovery required"):
                    with production_generation_read():
                        self.fail("reader accessed incomplete rollback")
                done = transaction.rollback_pending_to_legacy(
                    expected_candidate=candidate,
                )
                self.assertEqual(done["state"], "RECOVERED_LEGACY")
                with production_generation_read() as pinned:
                    self.assertEqual(pinned.generation, "legacy")
                self.assertFalse((root / transaction.POINTER_NAME).exists())
                self.assertFalse((root / transaction.JOURNAL_NAME).exists())
                self.assertTrue(
                    (root / ("recovered-pointer-" + candidate + ".json")).is_file()
                )
                self.assertTrue((root / "generations" / candidate).is_dir())
                self.assertEqual(legacy_sqlite.read_bytes(), b"original-RAG-index")

    def test_completed_rollback_crash_before_pointer_archive(self):
        self._run_case("before_archive")

    def test_completed_rollback_crash_after_pointer_archive(self):
        self._run_case("after_archive")
