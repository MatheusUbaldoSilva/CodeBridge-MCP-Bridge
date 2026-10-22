import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from installer.rag_p9b_external_recovery import recover_gui
from installer.rag_p9b_restart_readiness import REQUIRED


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        for rel in REQUIRED:
            p=self.root/rel
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(b"stub")

    def test_launch_returns_pid_and_explicitly_unverified_mcp(self):
        fake=Mock(pid=123)
        launch=Mock(return_value=fake)
        r=recover_gui(self.root,launch=launch,
                      probe=lambda pid:pid==123,
                      sleep=lambda _:None)
        self.assertEqual(r["state"],"GUI_PROCESS_RECOVERED")
        self.assertFalse(r["mcp_handshake_verified"])
        self.assertFalse(r["index_modified"])
        self.assertEqual(launch.call_count,1)

    def test_missing_binary_prevents_launch(self):
        (self.root/"runtime/python/pythonw.exe").unlink()
        launch=Mock()
        r=recover_gui(self.root,launch=launch)
        self.assertEqual(r["reason"],"RESTART_FILES_UNVERIFIED")
        launch.assert_not_called()

    def test_probe_failure_not_called_success(self):
        r=recover_gui(self.root,launch=lambda args,cwd:Mock(pid=123),
                      probe=lambda pid:False,sleep=lambda _:None,attempts=2)
        self.assertEqual(r["state"],"RECOVERY_PENDING")
        self.assertFalse(r["mcp_handshake_verified"] if "mcp_handshake_verified" in r else False)

    def test_launch_failure_refused(self):
        def fail(args,cwd): raise OSError("synthetic")
        r=recover_gui(self.root,launch=fail)
        self.assertEqual(r["reason"],"GUI_LAUNCH_FAILED")


if __name__=="__main__":
    unittest.main()
