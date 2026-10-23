import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_rollback_journal import RollbackJournal,read_journal


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

    def test_preexisting_file_refused(self):
        RollbackJournal(self.file)
        with self.assertRaises(FileExistsError):RollbackJournal(self.file)

    def test_non_shell_state_refused(self):
        w=RollbackJournal(self.file)
        with self.assertRaises(ValueError):w("EXTERNAL",{})
        self.assertEqual(read_journal(self.file)["count"],0)

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
