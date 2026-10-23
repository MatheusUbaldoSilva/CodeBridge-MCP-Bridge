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
    def test_complete_journal_refused_for_resume(self):
        import tempfile
        from pathlib import Path
        from installer.rag_p9b_rollback_journal import RollbackJournal
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"complete.jsonl"
            j=RollbackJournal(path)
            j("SHELL_COMBINED_RECOVERY_VERIFIED",{})
            with self.assertRaises(ValueError):RollbackJournal.resume(path)

if __name__=="__main__":
    unittest.main()
