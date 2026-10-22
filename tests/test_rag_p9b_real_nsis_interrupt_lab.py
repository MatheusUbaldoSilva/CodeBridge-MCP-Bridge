import json
import tempfile
import unittest
import uuid
from pathlib import Path
from installer.rag_p9b_real_nsis_interrupt_lab import recover,MARKER,SENTINEL

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.lab=Path(tempfile.gettempdir())/(MARKER+uuid.uuid4().hex)
        self.lab.mkdir()
        self.addCleanup(lambda:self.lab.rmdir() if self.lab.exists() and not list(self.lab.iterdir()) else None)
        self.journal=self.lab.parent/(self.lab.name+"_testjournal.jsonl")
        self.addCleanup(lambda:self.journal.unlink(missing_ok=True))
    def prepare(self, content=SENTINEL):
        (self.lab/"first.txt").write_bytes(content)
        self.journal.write_text(json.dumps({"state":"SHELL_NSIS_INTERRUPTED","lab":str(self.lab)})+"\n")
    def test_recovery_separate_entrypoint_contract(self):
        self.prepare()
        self.assertTrue(recover(self.lab,self.journal))
        self.assertFalse(self.lab.exists())
        self.assertEqual(len(self.journal.read_text().splitlines()),2)
    def test_unknown_file_refused(self):
        self.prepare(b"foreign")
        self.assertFalse(recover(self.lab,self.journal))
        (self.lab/"first.txt").unlink()
    def test_unexpected_extra_file_refused(self):
        self.prepare()
        (self.lab/"second.txt").write_bytes(b"extra")
        self.assertFalse(recover(self.lab,self.journal))
        for f in self.lab.iterdir():f.unlink()
    def test_bad_journal_refused(self):
        self.prepare()
        self.journal.write_text("{}\n")
        self.assertFalse(recover(self.lab,self.journal))
        (self.lab/"first.txt").unlink()
if __name__=="__main__":unittest.main()
