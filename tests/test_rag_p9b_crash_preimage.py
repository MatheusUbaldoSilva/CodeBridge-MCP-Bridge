import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_crash_preimage import create_crash_preimage,verify_crash_preimage


class FakeRegistry:
    def read_key(self,key):
        return {"exists":True,"values":{}}


class CrashPreimageTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.desktop=self.root/"desktop"
        self.desktop.mkdir()
        self.appdata=self.root/"appdata"
        self.menu=self.appdata/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
        self.menu.mkdir(parents=True)
        self.link=self.menu/"CodeBridge.lnk"
        self.link.write_bytes(b"preimage-test")
        self.file=self.root/"preimage.zip"

    def make(self,**kwargs):
        options=dict(appdata=self.appdata,desktop=self.desktop,
                     registry=FakeRegistry(),output=self.file)
        options.update(kwargs)
        return create_crash_preimage(**options)

    def test_verified_and_durable(self):
        r=self.make()
        self.assertEqual(r["state"],"CRASH_PREIMAGE_DURABLE")
        self.assertTrue(verify_crash_preimage(self.file,r["sha256"])["verified"])
        self.assertEqual(self.link.read_bytes(),b"preimage-test")

    def test_reuse_blocked(self):
        self.make()
        self.assertEqual(self.make()["reason"],"UNSAFE_OUTPUT")

    def test_modified_file_refused(self):
        r=self.make()
        self.file.write_bytes(b"tampered")
        self.assertEqual(verify_crash_preimage(self.file,r["sha256"])["reason"],
                         "SHA256_MISMATCH")

    def test_foreign_registry_value_refused(self):
        class Foreign:
            def read_key(self,key):
                return {"exists":True,"values":{"PASSWORD":{"type":1,"value":"secret"}}}
        self.assertEqual(self.make(registry=Foreign())["reason"],
                         "REGISTRY_SCOPE_UNVERIFIED")
        self.assertFalse(self.file.exists())

    def test_unsafe_link_refused(self):
        self.link.unlink()
        try:self.link.symlink_to(self.root/"missing")
        except OSError:self.skipTest("symlink unavailable")
        self.assertEqual(self.make()["reason"],"SHORTCUT_UNSAFE")


if __name__=="__main__":
    unittest.main()
