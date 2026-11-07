import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "app_rewrite"), str(ROOT)]
from PySide6.QtWidgets import QApplication  # noqa: E402
import rag_sync_bar as bar_module  # noqa: E402
from rag.runtime import knowledge_sync as sync  # noqa: E402


class FakeFlow:
    def __init__(self, files):
        self.files = dict(files)
        self.calls = []
        self.states = ["RUNNING", "READY_FOR_REVIEW"]

    def preview(self, project_id, root, paths=None):
        self.calls.append(("preview", paths))
        chosen = self.files if paths is None else {p: self.files[p] for p in paths if p in self.files}
        return {"sources": [{"path": p, "sha256": h} for p, h in chosen.items()], "review_sha256": "r" * 64}

    def queue(self, project_id, root, paths, review):
        self.calls.append(("queue", list(paths)))
        return {"job_id": "a" * 32}

    def start(self, job_id):
        self.calls.append(("start", job_id))

    def status(self, job_id):
        return {"state": self.states.pop(0) if self.states else "READY_FOR_REVIEW"}

    def control(self, job_id, action):
        self.calls.append(("control", action))

    def activation_review(self, project_id, job_id, remove_paths=None):
        self.calls.append(("review", remove_paths))
        return {"mode": "MERGE", "review_sha256": "m" * 64, "removed_paths": remove_paths or []}

    def activate(self, project_id, job_id, review, confirmation, progress=None):
        self.calls.append(("activate", confirmation, review.get("removed_paths")))
        return {"transaction": "t" * 32, "documents": 3}


class KnowledgeSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = Path(self.tmp.name) / "sync.json"
        self.folder = Path(self.tmp.name) / "src"
        self.folder.mkdir()

    def test_settings_roundtrip_and_validation(self):
        self.assertEqual(sync.settings("p", self.settings)["mode"], "OFF")
        sync.update_settings("p", self.settings, mode="AUTO", folder=str(self.folder))
        self.assertEqual(sync.settings("p", self.settings)["mode"], "AUTO")
        self.assertEqual(sync.settings("outro", self.settings)["mode"], "OFF")
        with self.assertRaises(sync.KnowledgeSyncError):
            sync.update_settings("p", self.settings, mode="TALVEZ")

    def test_changes_split_into_added_changed_removed(self):
        flow = FakeFlow({"a.py": "1", "b.py": "2-novo", "d.py": "4"})
        changes = sync.compute_changes("p", self.folder, flow=flow,
                                       hashes=lambda pid: {"a.py": "1", "b.py": "2", "c.py": "3"})
        self.assertEqual((changes["added"], changes["changed"], changes["removed"]),
                         (["d.py"], ["b.py"], ["c.py"]))
        self.assertEqual(changes["total"], 3)
        with self.assertRaises(sync.KnowledgeSyncError):
            sync.compute_changes("p", self.folder / "sumiu", flow=flow, hashes=lambda pid: {})

    def test_apply_indexes_changed_and_removes_deleted_in_one_merge(self):
        flow = FakeFlow({"b.py": "2-novo", "d.py": "4"})
        changes = {"folder": str(self.folder), "added": ["d.py"], "changed": ["b.py"], "removed": ["c.py"]}
        steps = []
        result = sync.apply_changes("p", changes, flow=flow, progress=steps.append,
                                    sleep=lambda s: None, path=self.settings)
        self.assertEqual(result["state"], "SYNCED")
        self.assertEqual(result["mode"], "MERGE")
        self.assertIn(("queue", ["b.py", "d.py"]), flow.calls)
        self.assertIn(("review", ["c.py"]), flow.calls)
        self.assertIn(("activate", "p", ["c.py"]), flow.calls)
        last = sync.settings("p", self.settings)["last"]
        self.assertEqual((last["added"], last["changed"], last["removed"]), (1, 1, 1))
        self.assertTrue(steps)

    def test_apply_refuses_when_folder_changed_during_check(self):
        flow = FakeFlow({"b.py": "2"})
        changes = {"folder": str(self.folder), "added": ["d.py"], "changed": ["b.py"], "removed": []}
        with self.assertRaises(sync.KnowledgeSyncError):
            sync.apply_changes("p", changes, flow=flow, sleep=lambda s: None, path=self.settings)
        self.assertFalse([c for c in flow.calls if c[0] == "queue"])

    def test_failed_indexing_does_not_activate(self):
        flow = FakeFlow({"b.py": "2"})
        flow.states = ["FAILED"]
        changes = {"folder": str(self.folder), "added": [], "changed": ["b.py"], "removed": []}
        with self.assertRaises(sync.KnowledgeSyncError):
            sync.apply_changes("p", changes, flow=flow, sleep=lambda s: None, path=self.settings)
        self.assertFalse([c for c in flow.calls if c[0] == "activate"])

    def test_nothing_to_do(self):
        changes = {"folder": str(self.folder), "added": [], "changed": [], "removed": []}
        self.assertEqual(sync.apply_changes("p", changes, flow=FakeFlow({}), path=self.settings)["state"],
                         "UP_TO_DATE")

    def test_fingerprint_follows_file_changes_and_skips_git(self):
        (self.folder / "a.py").write_text("1", encoding="utf-8")
        first = sync.fingerprint(self.folder)
        (self.folder / ".git").mkdir()
        (self.folder / ".git" / "HEAD").write_text("x", encoding="utf-8")
        self.assertEqual(sync.fingerprint(self.folder), first)
        (self.folder / "b.py").write_text("2", encoding="utf-8")
        self.assertNotEqual(sync.fingerprint(self.folder), first)

class FakeSync:
    def __init__(self, supported=True, mode="OFF", folder=None):
        self.ok = supported
        self.state = {"mode": mode, "folder": folder, "last": None}
        self.saved = []
        self.fp = "fp1"
        self.changes = {"folder": folder or "C:/proj", "added": ["n.py"], "changed": ["c.py"],
                        "removed": [], "total": 2}
        self.applied = []
        self.fail = None
        self.diffs = 0
        self.undone = 0

    def supported(self, project_id):
        return self.ok

    def settings(self, project_id):
        return dict(self.state)

    def update_settings(self, project_id, **changes):
        self.saved.append(changes)
        self.state.update(changes)

    def can_undo(self, project_id):
        return False

    def fingerprint(self, folder):
        return self.fp

    def compute_changes(self, project_id, folder):
        self.diffs += 1
        return dict(self.changes, folder=folder)

    def apply_changes(self, project_id, changes, progress=None):
        if progress:
            progress("Indexando 2 arquivo(s)")
        if self.fail:
            raise RuntimeError(self.fail)
        self.applied.append(changes)
        return {"state": "SYNCED", "mode": "MERGE", "added": 1, "changed": 1, "removed": 0,
                "at": "2026-11-07T16:00:00+00:00"}

    def undo_last(self, project_id):
        self.undone += 1
        return {}


class InlineBar(bar_module.KnowledgeSyncBar):
    def _start(self, worker):
        worker()
        self._drain()


class SyncBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make(self, fake, confirm=True):
        bar = InlineBar(sync=fake, ask_folder=lambda pid: "C:/proj", confirm=lambda *a: confirm)
        bar._check_timer.stop()
        changed = []
        bar.knowledge_changed.connect(changed.append)
        bar.set_project("proj")
        return bar, changed

    def test_unsupported_project_is_locked(self):
        bar, _ = self.make(FakeSync(supported=False))
        self.assertFalse(bar.buttons["AUTO"].isEnabled())
        self.assertIn("pr" + chr(0xF3) + "prio", bar.status.text())
        self.assertFalse(bar.check())

    def test_reload_unlocks_after_project_is_activated(self):
        fake = FakeSync(supported=False)
        bar, _ = self.make(fake)
        self.assertFalse(bar.buttons["MANUAL"].isEnabled())
        fake.ok = True
        bar.reload()
        self.assertTrue(bar.supported)
        self.assertTrue(bar.buttons["MANUAL"].isEnabled())
        self.assertIn("Desligado", bar.status.text())

    def test_tooltips_explain_each_mode(self):
        bar, _ = self.make(FakeSync())
        self.assertIn("sozinho", bar.buttons["AUTO"].toolTip())
        self.assertIn("Atualizar agora", bar.buttons["MANUAL"].toolTip())
        self.assertIn("Indexar", bar.buttons["OFF"].toolTip())

    def test_manual_warns_and_waits_for_click(self):
        fake = FakeSync()
        bar, changed = self.make(fake)
        bar.choose_mode("MANUAL")
        self.assertEqual(bar.mode, "MANUAL")
        self.assertEqual(fake.state["mode"], "MANUAL")
        self.assertEqual(fake.applied, [])
        self.assertIn("2 arquivos mudaram", bar.status.text())
        self.assertTrue(bar.apply_button.isVisibleTo(bar))
        bar.apply_now()
        self.assertEqual(len(fake.applied), 1)
        self.assertEqual(changed, ["proj"])
        self.assertTrue(bar.undo_button.isVisibleTo(bar))
        self.assertFalse(bar.apply_button.isVisibleTo(bar))

    def test_auto_needs_confirmation_then_applies_alone(self):
        fake = FakeSync()
        bar, _ = self.make(fake, confirm=False)
        bar.choose_mode("AUTO")
        self.assertEqual(bar.mode, "OFF")
        self.assertEqual(fake.saved, [])
        bar._confirm = lambda *a: True
        bar.choose_mode("AUTO")
        self.assertEqual(fake.state["mode"], "AUTO")
        self.assertEqual(len(fake.applied), 1)

    def test_auto_waits_for_folder_to_settle(self):
        fake = FakeSync(mode="AUTO", folder="C:/proj")
        fake.changes["total"] = 0
        fake.changes["added"], fake.changes["changed"] = [], []
        bar, _ = self.make(fake)
        self.assertEqual(fake.diffs, 1)
        fake.fp = "fp2"
        fake.changes.update(added=["n.py"], total=1)
        bar.check()
        self.assertEqual(fake.diffs, 1)
        bar.check()
        self.assertEqual(fake.diffs, 2)
        self.assertEqual(len(fake.applied), 1)
        bar.check()
        self.assertEqual(fake.diffs, 2)

    def test_failed_update_is_shown_and_not_retried_for_same_files(self):
        fake = FakeSync(mode="AUTO", folder="C:/proj")
        fake.fail = "disco cheio"
        bar, _ = self.make(fake)
        self.assertIn("disco cheio", bar.status.text())
        bar._last_fp = None
        bar.check()
        self.assertEqual(fake.applied, [])

    def test_undo_in_auto_switches_to_manual(self):
        fake = FakeSync(mode="AUTO", folder="C:/proj")
        bar, changed = self.make(fake)
        self.assertTrue(bar.can_undo)
        bar.undo()
        self.assertEqual(fake.undone, 1)
        self.assertEqual(bar.mode, "MANUAL")
        self.assertEqual(fake.state["mode"], "MANUAL")
        self.assertIn("Manual", bar.status.text())


if __name__ == "__main__":
    unittest.main()