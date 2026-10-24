import multiprocessing
import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_rollback_journal import RollbackJournal,read_journal


def simultaneous_append_worker(path, ready, go, results):
    from installer.rag_p9b_rollback_journal import RollbackJournal
    try:
        resumed=RollbackJournal.resume(path)
        ready.put("ready")
        if not go.wait(10):
            results.put("timeout")
            return
        resumed("SHELL_COMBINED_FILE_CHECKED",{"postverified":True})
        results.put("written")
    except ValueError as error:
        results.put(str(error))

class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file=Path(self.temp.name)/"journal.jsonl"

    def test_creation_and_append(self):
        w=RollbackJournal(self.file)
        w("SHELL_RESTORE_ARMED",{"files":5,"password":"DO_NOT_PERSIST"})
        w("SHELL_BACKEND_WRITTEN",{})
        self.assertEqual(read_journal(self.file)["count"],2)
        self.assertEqual(read_journal(self.file)["last_state"],"SHELL_BACKEND_WRITTEN")
        self.assertNotIn("DO_NOT_PERSIST",self.file.read_text(encoding="utf-8"))

    def test_two_resumed_processes_only_one_append_succeeds(self):
        ctx=multiprocessing.get_context("spawn")
        journal=RollbackJournal(self.file)
        journal("SHELL_COMBINED_RECOVERY_ARMED",{})
        ready=ctx.Queue()
        go=ctx.Event()
        results=ctx.Queue()
        workers=[ctx.Process(target=simultaneous_append_worker,
            args=(str(self.file),ready,go,results)) for _ in range(2)]
        try:
            for worker in workers:
                worker.start()
            self.assertEqual(ready.get(timeout=10),"ready")
            self.assertEqual(ready.get(timeout=10),"ready")
            go.set()
            observed=[results.get(timeout=10) for _ in workers]
            self.assertEqual(sorted(observed),["JOURNAL_SEQUENCE_CHANGED","written"])
            for worker in workers:
                worker.join(timeout=10)
                self.assertEqual(worker.exitcode,0)
            self.assertEqual(read_journal(self.file)["count"],2)
        finally:
            go.set()
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                worker.join(timeout=5)
    def test_preexisting_file_refused(self):
        RollbackJournal(self.file)
        with self.assertRaises(FileExistsError):RollbackJournal(self.file)

    def test_journal_replacement_with_link_is_refused_before_append(self):
        from unittest.mock import patch
        journal=RollbackJournal(self.file)
        original=Path.is_symlink
        with patch.object(Path,"is_symlink",
                          lambda item:True if item==self.file else original(item)):
            with self.assertRaisesRegex(ValueError,"JOURNAL_PATH_INVALID"):
                journal("SHELL_RESTORE_ARMED",{})
        self.assertEqual(read_journal(self.file)["count"],0)

    def test_stale_resumed_writer_rejects_second_writer_event(self):
        w=RollbackJournal(self.file)
        w("SHELL_COMBINED_RECOVERY_ARMED",{})
        resumed=RollbackJournal.resume(self.file)
        w("SHELL_COMBINED_FILE_CHECKED",{"postverified":True})
        with self.assertRaisesRegex(ValueError,"JOURNAL_SEQUENCE_CHANGED"):
            resumed("SHELL_DETACHED_SHELL_VERIFIED",{})
        self.assertEqual(read_journal(self.file)["count"],2)

    def test_writer_refuses_tampered_journal_before_append(self):
        w=RollbackJournal(self.file)
        w("SHELL_COMBINED_RECOVERY_ARMED",{})
        with self.file.open("ab") as stream:
            stream.write(b"{corrupted}\n")
        before=self.file.read_bytes()
        with self.assertRaisesRegex(ValueError,"JOURNAL_SEQUENCE_CHANGED"):
            w("SHELL_COMBINED_FILE_CHECKED",{})
        self.assertEqual(self.file.read_bytes(),before)
    def test_non_shell_state_refused(self):
        w=RollbackJournal(self.file)
        with self.assertRaises(ValueError):w("EXTERNAL",{})
        self.assertEqual(read_journal(self.file)["count"],0)

    def test_boolean_sequence_and_invalid_state_refused(self):
        for raw in ('{"seq":true,"state":"SHELL_ARMED","details":{}}',
                    '{"seq":1,"state":"READY","details":{}}',
                    '{"seq":1,"state":"SHELL_ARMED","details":null}',
                    '[]'):
            with self.subTest(raw=raw):
                self.file.write_text(raw,encoding="utf-8")
                self.assertEqual(read_journal(self.file)["state"],"JOURNAL_UNVERIFIED")

    def test_duplicate_json_keys_refused(self):
        self.file.write_text('{"seq":1,"seq":1,"state":"SHELL_ARMED","details":{}}',encoding="utf-8")
        self.assertEqual(read_journal(self.file)["state"],"JOURNAL_UNVERIFIED")

    def test_nonfinite_json_number_refused(self):
        for value in ("NaN","Infinity","-Infinity"):
            with self.subTest(value=value):
                self.file.write_text('{"seq":1,"state":"SHELL_ARMED","details":{"files":'+value+'}}',encoding="utf-8")
                self.assertEqual(read_journal(self.file)["state"],"JOURNAL_UNVERIFIED")

    def test_valid_json_without_newline_is_not_committed(self):
        self.file.write_text(
            '{"seq":1,"state":"SHELL_RESTORE_ARMED","details":{}}',
            encoding="utf-8")
        self.assertEqual(read_journal(self.file)["state"],"JOURNAL_UNVERIFIED")

    def test_journal_metadata_access_error_is_refused(self):
        from unittest.mock import patch
        with patch.object(Path,"stat",side_effect=PermissionError("access denied")):
            self.assertEqual(read_journal(self.file)["state"],"JOURNAL_UNVERIFIED")

    def test_invalid_utf8_is_refused_fail_closed(self):
        self.file.write_bytes(b"\xff\xfe\n")
        self.assertEqual(read_journal(self.file)["state"],"JOURNAL_UNVERIFIED")
        with self.assertRaises(ValueError):
            RollbackJournal.resume(self.file)

    def test_corrupted_seq_refused(self):
        self.file.write_text('{"seq":9,"state":"SHELL_BAD"}',encoding="utf-8")
        self.assertEqual(read_journal(self.file)["state"],"JOURNAL_UNVERIFIED")


class ResumeJournalTests(unittest.TestCase):
    def test_incomplete_journal_resumes_with_incrementing_sequence(self):
        import tempfile
        from pathlib import Path
        from installer.rag_p9b_rollback_journal import RollbackJournal,read_journal
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"resume.jsonl"
            j=RollbackJournal(path)
            j("SHELL_COMBINED_RECOVERY_ARMED",{})
            another=RollbackJournal.resume(path)
            another("SHELL_COMBINED_FILE_CHECKED",{"postverified":True})
            self.assertEqual(read_journal(path)["count"],2)
    def test_file_restore_completed_journal_refused_for_resume(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"complete-files.jsonl"
            journal=RollbackJournal(path)
            journal("SHELL_NSIS_FULL_SCOPE_INTERRUPTED",{})
            journal("SHELL_PRODUCTION_FILE_RESTORED",{"postverified":True})
            with self.assertRaises(ValueError):
                RollbackJournal.resume(path)

    def test_combined_file_completed_does_not_close_shell_transaction(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"combined-file.jsonl"
            journal=RollbackJournal(path)
            journal("SHELL_DETACHED_COMBINED_ARMED",{})
            journal("SHELL_PRODUCTION_FILE_RESTORED",{"postverified":True})
            journal("SHELL_DETACHED_COMBINED_EXCEPTION",{"type":"OSError"})
            resumed=RollbackJournal.resume(path)
            resumed("SHELL_DETACHED_COMBINED_VERIFIED",{"postverified":True})
            with self.assertRaises(ValueError):
                RollbackJournal.resume(path)

    def test_combined_file_only_terminal_event_is_not_combined_completion(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"interrupted-between-files-and-shell.jsonl"
            j=RollbackJournal(path)
            j("SHELL_DETACHED_COMBINED_ARMED",{})
            j("SHELL_PRODUCTION_FILE_RESTORED",{"postverified":True})
            resumed=RollbackJournal.resume(path)
            resumed("SHELL_DETACHED_SHELL_VERIFIED",{"postverified":True})
            resumed("SHELL_DETACHED_COMBINED_VERIFIED",{"postverified":True})
            with self.assertRaises(ValueError):
                RollbackJournal.resume(path)

    def test_combined_journal_requires_same_transaction_identity(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"identity-bound.jsonl"
            j=RollbackJournal(path)
            j("SHELL_DETACHED_COMBINED_ARMED",{"transaction_sha256":"a"*64})
            j("SHELL_PRODUCTION_FILE_RESTORED",{"postverified":True})
            self.assertEqual(
                RollbackJournal.resume(path,expected_transaction_sha256="a"*64)._sequence,2)
            with self.assertRaises(ValueError):
                RollbackJournal.resume(path,expected_transaction_sha256="b"*64)

    def test_combined_journal_rejects_missing_identity(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"unbound.jsonl"
            j=RollbackJournal(path)
            j("SHELL_DETACHED_COMBINED_ARMED",{})
            with self.assertRaises(ValueError):
                RollbackJournal.resume(path,expected_transaction_sha256="a"*64)

    def test_lifecycle_journal_requires_bound_identity_on_resume(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"lifecycle-bound.jsonl"
            initial=RollbackJournal(path)
            initial("SHELL_DETACHED_LIFECYCLE_ARMED",
                    {"transaction_sha256":"a"*64})
            initial("SHELL_DETACHED_SHUTDOWN_SIGNALED",{})
            with self.assertRaises(ValueError):
                RollbackJournal.resume(path,expected_transaction_sha256="b"*64)
            resumed=RollbackJournal.resume(path,expected_transaction_sha256="a"*64)
            self.assertEqual(resumed.bound_transaction_sha256,"a"*64)
            self.assertEqual(resumed._sequence,2)

    def test_incomplete_external_lifecycle_journal_is_observable_for_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"lifecycle.jsonl"
            initial=RollbackJournal(path)
            initial("SHELL_DETACHED_LIFECYCLE_ARMED",{})
            initial("SHELL_DETACHED_SHUTDOWN_SIGNALED",{})
            recovered=RollbackJournal.resume(path)
            self.assertEqual(recovered._sequence,2)
            self.assertTrue(recovered.resumed)
            recovered("SHELL_DETACHED_LIFECYCLE_REVIEW_REQUIRED",{})
            self.assertEqual(read_journal(path)["last_state"],
                             "SHELL_DETACHED_LIFECYCLE_REVIEW_REQUIRED")

    def test_detached_combined_journal_resumes_after_crash(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"combined.jsonl"
            j=RollbackJournal(path)
            j("SHELL_DETACHED_COMBINED_ARMED",{})
            j("SHELL_DETACHED_FILES_VERIFIED",{"postverified":True})
            again=RollbackJournal.resume(path)
            again("SHELL_DETACHED_SHELL_VERIFIED",{"postverified":True})
            again("SHELL_DETACHED_COMBINED_VERIFIED",{"postverified":True})
            self.assertEqual(read_journal(path)["count"],4)
            with self.assertRaises(ValueError):
                RollbackJournal.resume(path)

    def test_complete_journal_refused_for_resume(self):
        import tempfile
        from pathlib import Path
        from installer.rag_p9b_rollback_journal import RollbackJournal
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"complete.jsonl"
            j=RollbackJournal(path)
            j("SHELL_COMBINED_RECOVERY_VERIFIED",{})
            with self.assertRaises(ValueError):RollbackJournal.resume(path)

class JournalTamperResumeTests(unittest.TestCase):
    def test_rejects_completed_history_with_appended_event(self):
        import json,tempfile
        from pathlib import Path
        from installer.rag_p9b_rollback_journal import RollbackJournal
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/"tampered.jsonl"
            journal=RollbackJournal(target)
            journal("SHELL_COMBINED_RECOVERY_VERIFIED",{})
            journal("SHELL_BACKEND_ARMED",{})
            with self.assertRaises(ValueError):RollbackJournal.resume(target)
    def test_refuses_unscoped_incomplete_state(self):
        import json,tempfile
        from pathlib import Path
        from installer.rag_p9b_rollback_journal import RollbackJournal
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/"wrong-state.jsonl"
            target.write_text(json.dumps({"seq":1,"state":"OTHER_EVENT","details":{}})+"\n")
            with self.assertRaises(ValueError):RollbackJournal.resume(target)

class JournalStartGateTests(unittest.TestCase):
    def test_refuses_arbitrary_first_shell_event(self):
        import tempfile
        from pathlib import Path
        from installer.rag_p9b_rollback_journal import RollbackJournal
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/"invalid-start.jsonl"
            journal=RollbackJournal(target)
            journal("SHELL_BACKEND_ARMED",{})
            with self.assertRaises(ValueError):RollbackJournal.resume(target)

if __name__=="__main__":
    unittest.main()
