import json
import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_transaction_identity import NAMES
from installer.rag_p9b_frozen_disposable_bundle import freeze_disposable_bundle, verify_disposable_bundle


class FrozenDisposableBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scopes = {}
        for name in ("installed", "appdata", "desktop"):
            path = self.root / name
            path.mkdir()
            self.scopes[name] = path
        self.sources = {}
        for name in NAMES:
            path = self.root / (name + ".src")
            path.write_bytes(("original-" + name).encode())
            self.sources[name] = path
        self.out = self.root / "bundle"

    def freeze(self, **changes):
        kw = dict(destination=self.out, artifacts=self.sources, source_commit="a" * 40,
                  transaction_id="b" * 32, hkcu_prefix="Software\\CodeBridge_P9B_Lab\\test",
                  temp_root=self.root, **self.scopes)
        kw.update(changes)
        return freeze_disposable_bundle(**kw)

    def test_freeze_and_verify_exact_four(self):
        result = self.freeze()
        self.assertTrue(result["frozen"], result)
        self.assertFalse(result["trusted_origin"])
        proof = verify_disposable_bundle(result["manifest"], result["manifest_sha256"],
                                         temp_root=self.root)
        self.assertTrue(proof["verified"], proof)
        self.assertEqual(proof["transaction_id"], "b" * 32)
        self.assertEqual(len(json.loads(Path(result["manifest"]).read_text())["artifacts"]), 4)

    def test_changed_source_after_freeze_does_not_change_frozen_bundle(self):
        result = self.freeze()
        self.sources["installer"].write_bytes(b"changed")
        self.assertTrue(verify_disposable_bundle(result["manifest"], result["manifest_sha256"],
                                                  temp_root=self.root)["verified"])

    def test_changed_copy_refused(self):
        result = self.freeze()
        (self.out / "installer.bin").write_bytes(b"tampered")
        self.assertEqual(verify_disposable_bundle(result["manifest"], result["manifest_sha256"],
                                                 temp_root=self.root)["reason"],
                         "FROZEN_ARTIFACT_CHANGED")

    def test_wrong_digest_refused(self):
        result = self.freeze()
        self.assertEqual(verify_disposable_bundle(result["manifest"], "f" * 64,
                                                 temp_root=self.root)["reason"],
                         "MANIFEST_DIGEST_MISMATCH")

    def test_non_lab_scope_refused_before_create(self):
        result = self.freeze(installed=Path(self.root.anchor) / "outside_p9b")
        self.assertEqual(result["reason"], "SCOPE_OUTSIDE_LAB")
        self.assertFalse(self.out.exists())

    def test_forged_manifest_with_matching_digest_cannot_expand_scope(self):
        import hashlib
        result = self.freeze()
        path = Path(result["manifest"])
        data = json.loads(path.read_text(encoding="utf-8"))
        data["scopes"]["installed"] = str(Path(self.root.anchor) / "unrelated")
        path.write_text(json.dumps(data), encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(verify_disposable_bundle(path, digest, temp_root=self.root)["reason"],
                         "SCOPE_OUTSIDE_LAB")

    def test_duplicate_manifest_keys_refused_even_with_matching_digest(self):
        import hashlib
        result = self.freeze()
        path = Path(result["manifest"])
        raw = path.read_text(encoding="utf-8")
        path.write_text('{"schema":1,' + raw.lstrip()[1:], encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(verify_disposable_bundle(path, digest, temp_root=self.root)["reason"],
                         "BUNDLE_CHECK_FAILED")

    def test_custom_temp_root_cannot_expand_to_filesystem_root(self):
        self.assertEqual(self.freeze(temp_root=Path(self.root.anchor))["reason"],
                         "TEMP_ROOT_UNTRUSTED")
    def test_reuse_bundle_refused(self):
        self.assertTrue(self.freeze()["frozen"])
        self.assertEqual(self.freeze()["reason"], "LAB_OUTPUT_NOT_NEW_OR_NOT_TEMP")

    def test_broad_hkcu_prefix_refused(self):
        self.assertEqual(self.freeze(hkcu_prefix="Software\\CodeBridge")["reason"],
                         "HKCU_SCOPE_INVALID")
        self.assertFalse(self.out.exists())

    def test_wrong_transaction_id_refused(self):
        self.assertEqual(self.freeze(transaction_id="z" * 32)["reason"],
                         "IDENTITY_INPUT_INVALID")

    def test_symlink_input_refused(self):
        link = self.root / "installer.link"
        try:
            link.symlink_to(self.sources["installer"])
        except (OSError, NotImplementedError):
            self.skipTest("symlink unavailable")
        self.sources["installer"] = link
        self.assertEqual(self.freeze()["reason"], "SOURCE_NOT_DISPOSABLE")


if __name__ == "__main__":
    unittest.main()