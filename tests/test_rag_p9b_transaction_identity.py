import tempfile,unittest
from pathlib import Path
from installer.rag_p9b_transaction_identity import NAMES,write_identity,verify_identity

class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.output=self.root/"identity.json"
        self.artifacts={}
        for name in NAMES:
            p=self.root/(name+".bin");p.write_bytes(name.encode())
            self.artifacts[name]=p
    def create(self):
        return write_identity(self.output,artifacts=self.artifacts,installed=self.root,
                              source_commit="a"*40)
    def test_exact_bound_files_verified(self):
        made=self.create()
        self.assertTrue(made["written"])
        self.assertTrue(verify_identity(self.output,made["manifest_sha256"])["verified"])
    def test_tampered_artifact_refused(self):
        made=self.create();self.artifacts["installer"].write_bytes(b"tampered")
        self.assertEqual(verify_identity(self.output,made["manifest_sha256"])["reason"],
                         "BOUND_ARTIFACT_CHANGED")
    def test_wrong_manifest_hash_refused(self):
        self.create()
        self.assertEqual(verify_identity(self.output,"f"*64)["reason"],"MANIFEST_HASH_MISMATCH")
    def test_reuse_output_refused(self):
        self.create()
        self.assertEqual(self.create()["reason"],"IDENTITY_OUTPUT_NOT_NEW")
    def test_invalid_source_commit_refused_before_manifest_write(self):
        for commit in ("z"*40,"A"*40,"a"*39,True):
            with self.subTest(commit=commit):
                result=write_identity(
                    self.output,artifacts=self.artifacts,
                    installed=self.root,source_commit=commit)
                self.assertFalse(result["written"])
                self.assertFalse(self.output.exists())

    def test_non_mapping_artifacts_are_refused(self):
        result=write_identity(
            self.output,artifacts=["installer"],
            installed=self.root,source_commit="a"*40)
        self.assertFalse(result["written"])
        self.assertFalse(self.output.exists())

    def test_missing_artifact_refused(self):
        self.artifacts.pop("shell_snapshot")
        self.assertEqual(self.create()["reason"],"ARTIFACT_SET_INVALID")
if __name__=="__main__":unittest.main()
