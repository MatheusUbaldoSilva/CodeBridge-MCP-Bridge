import json
import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_transaction_identity import NAMES,write_identity
from installer.rag_p9b_detached_combined_identity_gate import assess_detached_identity


class IdentityBindingTests(unittest.TestCase):
    def setUp(self):
        ctx=tempfile.TemporaryDirectory()
        self.addCleanup(ctx.cleanup)
        self.root=Path(ctx.name)
        self.installed=self.root/"installed"
        self.installed.mkdir()
        self.artifacts={}
        for name in NAMES:
            file=self.root/(name+".bin")
            file.write_bytes(name.encode())
            self.artifacts[name]=file
        self.identity=self.root/"identity.json"
        self.commit="a"*40
        result=write_identity(self.identity,artifacts=self.artifacts,
                              installed=self.installed,source_commit=self.commit)
        assert result["written"]
        self.hash=result["manifest_sha256"]

    def probe(self,**kwargs):
        return assess_detached_identity(**(dict(
            manifest=self.identity,manifest_sha256=self.hash,
            installed=self.installed,expected_source_commit=self.commit)|kwargs))

    def test_four_artifacts_bound_without_authorizing_install(self):
        state=self.probe()
        self.assertEqual(state["state"],"DETACHED_IDENTITY_OBSERVED_ONLY")
        self.assertTrue(state["identity_verified"])
        self.assertFalse(state["verified"])
        self.assertFalse(state["cutover_authorized"])

    def test_changed_installer_bytes_refused(self):
        self.artifacts["installer"].write_bytes(b"changed")
        self.assertEqual(self.probe()["reason"],"FOUR_ARTIFACT_IDENTITY_INVALID")

    def test_changed_installation_path_refused(self):
        other=self.root/"other"
        other.mkdir()
        self.assertEqual(self.probe(installed=other)["reason"],
                         "INSTALLED_OR_SOURCE_COMMIT_MISMATCH")

    def test_source_commit_mismatch_refused(self):
        self.assertEqual(self.probe(expected_source_commit="b"*40)["reason"],
                         "INSTALLED_OR_SOURCE_COMMIT_MISMATCH")


if __name__=="__main__":
    unittest.main()
