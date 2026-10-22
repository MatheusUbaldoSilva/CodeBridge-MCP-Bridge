import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
import json
from installer.rag_p9b_shell_snapshot import (
    snapshot_shell_state,verify_shell_snapshot
)


class ShellSnapshotTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.desktop=self.root/"desktop"
        self.desktop.mkdir()
        self.appdata=self.root/"appdata"
        self.appdata.mkdir()
        self.output=self.root/"shell.zip"
        self.menu=self.appdata/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
        self.menu.mkdir(parents=True)

    def registry(self,key,names):
        return {"exists":True,"values":{}}

    def make(self,**kw):
        return snapshot_shell_state(appdata=self.appdata,desktop=self.desktop,
                                    snapshot=self.output,registry_values=kw.get("registry",self.registry))

    def test_full_snapshot_verified(self):
        (self.menu/"CodeBridge.lnk").write_bytes(b"lnk")
        s=self.make()
        self.assertEqual(s["state"],"SHELL_BACKUP_CREATED")
        v=verify_shell_snapshot(self.output)
        self.assertTrue(v["verified"])
        self.assertFalse(v["restore_performed"])

    def test_cannot_replace_existing_archive(self):
        self.make()
        s=self.make()
        self.assertEqual(s["reason"],"TARGET_ALREADY_EXISTS_OR_PARENT_MISSING")

    def test_unknown_registry_value_fails_closed(self):
        s=self.make(registry=lambda key,names:{"exists":True,
             "values":{"PASSWORD":{"type":1,"value":"secret"}}})
        self.assertEqual(s["reason"],"UNEXPECTED_REGISTRY_VALUES")
        self.assertFalse(self.output.exists())

    def test_extra_member_refused(self):
        self.make()
        with ZipFile(self.output,"a") as z:
            z.writestr("unapproved.txt",b"extra")
        self.assertFalse(verify_shell_snapshot(self.output)["verified"])

    def test_unapproved_registry_value_refused(self):
        def bad(key,names):
            return {"exists":True,
                    "values":{"UNEXPECTED_SECRET":{"type":1,"value":"s"}}}
        r=self.make(registry=bad)
        self.assertFalse(r["created"])

    def test_shortcut_name_mutation_refused(self):
        self.make()
        with ZipFile(self.output,"r") as z:
            meta=json.loads(z.read("manifest.json"))
        meta["shortcuts"][0]["name"]="Different.lnk"
        self.output.unlink()
        with ZipFile(self.output,"w") as z:
            z.writestr("manifest.json",json.dumps(meta))
        self.assertFalse(verify_shell_snapshot(self.output)["verified"])

    def test_corrupt_snapshot_refused(self):
        self.output.write_bytes(b"corrupt")
        self.assertFalse(verify_shell_snapshot(self.output)["verified"])


if __name__=="__main__":
    unittest.main()
