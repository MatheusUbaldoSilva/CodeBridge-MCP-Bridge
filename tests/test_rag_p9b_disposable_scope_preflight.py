import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_transaction_identity import NAMES
from installer.rag_p9b_frozen_disposable_bundle import freeze_disposable_bundle
from installer.rag_p9b_disposable_scope_preflight import assess_disposable_scope


class DisposableScopePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.scopes={}
        for name in ("installed","appdata","desktop"):
            path=self.root/name
            path.mkdir()
            self.scopes[name]=path
        artifacts={}
        for name in NAMES:
            path=self.root/(name+".bin")
            path.write_bytes(name.encode())
            artifacts[name]=path
        self.frozen=freeze_disposable_bundle(
            self.root/"bundle", artifacts=artifacts, source_commit="a"*40,
            transaction_id="b"*32, hkcu_prefix="Software\\CodeBridge_P9B_Lab\\test",
            temp_root=self.root,**self.scopes)
        self.assertTrue(self.frozen["frozen"])

    def check(self, **changes):
        kw=dict(manifest=self.frozen["manifest"], manifest_sha256=self.frozen["manifest_sha256"],
                temp_root=self.root, registry_query=lambda key:{"exists":False,"value_names":[]},
                **self.scopes)
        kw.update(changes)
        return assess_disposable_scope(**kw)

    def test_isolated_scope_reports_exact_shell_count(self):
        proof=self.check()
        self.assertTrue(proof["verified"],proof)
        self.assertEqual(proof["shortcuts_observed"],5)
        self.assertEqual(proof["registry_keys_observed"],2)
        self.assertFalse(proof["cutover_authorized"])
        self.assertFalse(proof["nsis_executed"])

    def test_outside_installed_refused(self):
        proof=self.check(installed=Path(self.root.anchor)/"not_temp")
        self.assertEqual(proof["reason"],"BOUND_SCOPE_MISMATCH")

    def test_wrong_desktop_refused(self):
        other=self.root/"other_desktop"
        other.mkdir()
        self.assertEqual(self.check(desktop=other)["reason"],"BOUND_SCOPE_MISMATCH")

    def test_live_registry_without_injected_query_refused(self):
        self.assertEqual(self.check(registry_query=None)["reason"],
                         "INJECTED_REGISTRY_QUERY_REQUIRED")

    def test_symlinked_shortcut_parent_refused(self):
        parent = self.scopes["appdata"]/"Microsoft"
        redirect = self.root/"redirect"
        redirect.mkdir()
        try:
            parent.symlink_to(redirect,target_is_directory=True)
        except (OSError,NotImplementedError):
            self.skipTest("symlink unavailable")
        self.assertEqual(self.check()["reason"],"SHELL_PATH_REDIRECTED")
    def test_frozen_artifact_tamper_refused(self):
        (self.root/"bundle"/"installer.bin").write_bytes(b"modified")
        self.assertEqual(self.check()["reason"],"FROZEN_BUNDLE_UNVERIFIED")

    def test_registry_queries_only_isolated_prefix(self):
        queried=[]
        def record(key):
            queried.append(key)
            return {"exists":False,"value_names":[]}
        proof=self.check(registry_query=record)
        self.assertTrue(proof["verified"])
        self.assertEqual(len(queried),2)
        self.assertTrue(all(x.startswith("Software\\CodeBridge_P9B_Lab\\test\\") for x in queried))


if __name__=="__main__":
    unittest.main()