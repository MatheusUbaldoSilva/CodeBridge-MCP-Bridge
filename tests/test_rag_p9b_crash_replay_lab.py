import hashlib
import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_crash_preimage import create_crash_preimage
from installer.rag_p9b_crash_replay_lab import replay_preimage_scratch


class Registry:
    def read_key(self,key):
        return {"exists":True,"values":{}}


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.desktop=self.root/"desktop"
        self.desktop.mkdir()
        self.appdata=self.root/"appdata"
        menu=self.appdata/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
        menu.mkdir(parents=True)
        (menu/"CodeBridge.lnk").write_bytes(b"old-content")
        self.zip=self.root/"preimage.zip"
        created=create_crash_preimage(appdata=self.appdata,desktop=self.desktop,
                                      registry=Registry(),output=self.zip)
        self.assertTrue(created["created"])
        self.digest=created["sha256"]
        self.scratch=self.root/"scratch"

    def test_replay_from_real_zip_into_scratch(self):
        result=replay_preimage_scratch(self.zip,self.digest,self.scratch)
        self.assertEqual(result["state"],"CRASH_REPLAY_SCRATCH_VERIFIED")
        self.assertFalse(result["registry_modified"])
        self.assertEqual((self.scratch/"shortcut_0.bin").read_bytes(),b"old-content")
        self.assertEqual(result["reviewed_registry_keys"],2)

    def test_hash_mismatch_is_refused(self):
        result=replay_preimage_scratch(self.zip,"f"*64,self.scratch)
        self.assertEqual(result["reason"],"PREIMAGE_UNVERIFIED")
        self.assertFalse(self.scratch.exists())

    def test_existing_scratch_refused(self):
        self.scratch.mkdir()
        result=replay_preimage_scratch(self.zip,self.digest,self.scratch)
        self.assertEqual(result["reason"],"SCRATCH_NOT_FRESH")


if __name__=="__main__":
    unittest.main()
