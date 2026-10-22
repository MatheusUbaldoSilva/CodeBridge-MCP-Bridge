import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_poststart_health import check_local_poststart


class PostStartHealthTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        p=self.root/"app_rewrite"/"author_mcp_status.py"
        p.parent.mkdir(parents=True)
        p.write_text("class AuthorMCPStatus: pass")

    def test_local_online_still_requires_public_handshake(self):
        r=check_local_poststart(self.root,
             probe=lambda:{"state":"ONLINE","adapter_online":True,
                            "mcp_online":True})
        self.assertTrue(r["verified"])
        self.assertFalse(r["public_mcp_handshake_verified"])

    def test_adapter_down_fails(self):
        r=check_local_poststart(self.root,
             probe=lambda:{"state":"DEGRADED","adapter_online":False,
                            "mcp_online":True})
        self.assertFalse(r["verified"])

    def test_missing_source_fails_closed(self):
        (self.root/"app_rewrite"/"author_mcp_status.py").unlink()
        r=check_local_poststart(self.root)
        self.assertEqual(r["reason"],"HEALTH_PROBE_SOURCE_MISSING")

    def test_health_exception_fails_closed(self):
        def fail():raise OSError("fail")
        r=check_local_poststart(self.root,probe=fail)
        self.assertEqual(r["reason"],"HEALTH_PROBE_FAILED")


if __name__=="__main__":
    unittest.main()
