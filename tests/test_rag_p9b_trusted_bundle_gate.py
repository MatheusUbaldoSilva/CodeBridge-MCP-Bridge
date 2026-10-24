import hashlib
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from installer.rag_p9b_transaction_identity import NAMES
from installer.rag_p9b_frozen_disposable_bundle import freeze_disposable_bundle
from installer.rag_p9b_trusted_bundle_gate import verify_signed_frozen_bundle


class TrustedRootGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        scopes = {}
        for name in ("installed", "appdata", "desktop"):
            path = self.root / name
            path.mkdir()
            scopes[name] = path
        files = {}
        for name in NAMES:
            path = self.root / (name + ".src")
            path.write_bytes(name.encode())
            files[name] = path
        frozen = freeze_disposable_bundle(
            self.root / "frozen", artifacts=files, source_commit="a" * 40,
            transaction_id="b" * 32, hkcu_prefix="Software\\CodeBridge_P9B_Lab\\test",
            temp_root=self.root, **scopes)
        self.assertTrue(frozen["frozen"], frozen)
        self.manifest = frozen["manifest"]
        self.sha = frozen["manifest_sha256"]
        self.key = Ed25519PrivateKey.generate()
        self.pub = self.key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.signature = self.root / "signature.bin"
        self.signature.write_bytes(self.key.sign(Path(self.manifest).read_bytes()))

    def check(self, **extra):
        args = dict(manifest=self.manifest, signature=self.signature,
                    public_key=self.pub, expected_manifest_sha256=self.sha,
                    temp_root=self.root)
        args.update(extra)
        return verify_signed_frozen_bundle(**args)

    def test_valid_signature_not_independent_trust(self):
        proof = self.check()
        self.assertTrue(proof["signature_valid"])
        self.assertFalse(proof["verified"])
        self.assertEqual(proof["state"], "TRUST_ROOT_UNVERIFIED")
        self.assertEqual(proof["reason"], "INDEPENDENT_TRUST_ROOT_MISSING")

    def test_forged_caller_attestation_must_not_unlock(self):
        proof = self.check(trusted_root_proof={
            "independent": True, "protected": True,
            "public_key_sha256": hashlib.sha256(self.pub).hexdigest(),
            "authorized_purpose": "P9B_LAB_BUNDLE"})
        self.assertFalse(proof["trusted_origin"])
        self.assertFalse(proof["cutover_authorized"])

    def test_signature_mismatch_refused(self):
        other = Ed25519PrivateKey.generate()
        self.signature.write_bytes(other.sign(Path(self.manifest).read_bytes()))
        self.assertEqual(self.check()["reason"], "SIGNATURE_NOT_VERIFIED")

    def test_public_key_mismatch_refused(self):
        other = Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.assertEqual(self.check(public_key=other)["reason"], "SIGNATURE_NOT_VERIFIED")

    def test_modified_frozen_artifact_refused_before_signature(self):
        (self.root / "frozen" / "installer.bin").write_bytes(b"changed")
        proof = self.check()
        self.assertEqual(proof["reason"], "BUNDLE_INCONSISTENT")
        self.assertFalse(proof["verified"])

    def test_modified_manifest_refused(self):
        Path(self.manifest).write_bytes(b"{}")
        self.assertEqual(self.check()["reason"], "BUNDLE_INCONSISTENT")


if __name__ == "__main__":
    unittest.main()