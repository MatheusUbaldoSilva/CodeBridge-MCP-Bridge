import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from installer.rag_p9b_atomic_shortcut_restore import write_atomic_shortcut

class AtomicShortcutTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.link=self.root/"CodeBridge.lnk"
        self.link.write_bytes(b"original")
    def test_atomic_replace(self):
        write_atomic_shortcut(self.link,b"new-content")
        self.assertEqual(self.link.read_bytes(),b"new-content")
        self.assertEqual(list(self.root.glob(".cb-p9b-*")),[])
    def test_os_replace_failure_preserves_original(self):
        with patch("installer.rag_p9b_atomic_shortcut_restore.os.replace",side_effect=OSError("injected")):
            with self.assertRaises(OSError):write_atomic_shortcut(self.link,b"new-content")
        self.assertEqual(self.link.read_bytes(),b"original")
        self.assertEqual(list(self.root.glob(".cb-p9b-*")),[])
    def test_missing_parent_refused(self):
        with self.assertRaises(ValueError):write_atomic_shortcut(self.root/"missing"/"x.lnk",b"content")
    def test_large_payload_refused(self):
        with self.assertRaises(ValueError):write_atomic_shortcut(self.link,b"a"*65537)
    def test_symlink_refused_when_available(self):
        other=self.root/"other";other.write_bytes(b"other")
        self.link.unlink()
        try:self.link.symlink_to(other)
        except OSError as exc:
            if getattr(exc,"winerror",None)==1314:self.skipTest("symlink privilege unavailable")
            raise
        with self.assertRaises(ValueError):write_atomic_shortcut(self.link,b"oops")
        self.assertEqual(other.read_bytes(),b"other")
if __name__=="__main__":unittest.main()
