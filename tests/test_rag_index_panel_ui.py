import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_rewrite"))
from PySide6.QtWidgets import QApplication  # noqa: E402
import rag_index_panel as module  # noqa: E402

SOURCES = [{"path": "src/a.py", "index_kind": "CODE", "sha256": "a" * 64},
           {"path": "docs/b.md", "index_kind": "TEXT", "sha256": "b" * 64}]


class FakeFlow:
    def __init__(self):
        self.calls = []
        self.job = None
        self.state = "RUNNING"

    def current_job(self, project_id):
        return self.job

    def pending_undo(self, project_id):
        return None

    def preview(self, project_id, root, paths=None):
        self.calls.append(("preview", paths))
        return {"sources": SOURCES if not paths else [s for s in SOURCES if s["path"] in paths],
                "candidate_count": 2, "review_sha256": "r" * 64}

    def queue(self, project_id, root, paths, sha):
        self.calls.append(("queue", paths, sha))
        return {"job_id": "j" * 32, "state": "QUEUED"}

    def start(self, job_id):
        self.calls.append(("start", job_id))
        return {"state": "PROCESS_STARTED_UNVERIFIED", "pid": 1}

    def status(self, job_id):
        return {"state": self.state, "vectors_done": 5, "vectors_expected": 10,
                "percent": 50, "percent_known": True}

    def control(self, job_id, action):
        self.calls.append(("control", action))
        return {"state": "CANCELLED" if action == "CANCEL" else "PAUSE_REQUESTED"}

    def activation_review(self, project_id, job_id):
        return {"mode": "MERGE", "added_paths": ["docs/b.md"], "replaced_paths": ["src/a.py"],
                "documents_before": 5, "documents_after": 6, "chunks_before": 50,
                "chunks_after": 58, "review_sha256": "m" * 64}

    def activate(self, project_id, job_id, review, confirmation, progress=None):
        self.calls.append(("activate", confirmation, review["review_sha256"]))
        return {"mode": "MERGE", "added_files": ["docs/b.md"], "replaced_files": ["src/a.py"],
                "documents": 6, "transaction": "t" * 32}

    def undo(self, project_id):
        self.calls.append(("undo", project_id))
        return {"mode": "MERGE"}


class InlineThread:
    def __init__(self, target=None, **kwargs):
        self.target = target

    def start(self):
        self.target()


class IndexPanelTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        threads = patch.object(module.threading, "Thread", InlineThread)
        threads.start()
        self.addCleanup(threads.stop)
        self.flow = FakeFlow()
        self.panel = module.KnowledgeIndexPanel(flow=self.flow)
        self.addCleanup(self.panel.close)
        self.panel.set_project("demo")
        self.panel._drain_events()

    def _run(self, call):
        call()
        self.panel._drain_events()

    def _confirm(self, accept=True):
        return patch.object(module.ConfirmByNameDialog, "exec", return_value=1 if accept else 0), \
            patch.object(module.ConfirmByNameDialog, "confirmation", return_value="demo")

    def test_full_flow_choose_index_activate_undo(self):
        self._run(lambda: self.panel.set_root("C:/pasta"))
        self.assertEqual(self.panel.selector.leaf_count(), 2)
        self.assertEqual(self.panel.primary.text(), "Indexar 2 arquivo(s)")
        self.assertIn("1 c\u00f3digo", self.panel.footer_text.text())
        dialog, name = self._confirm()
        with dialog, name:
            self._run(self.panel.primary_action)
        self.assertIn(("queue", None, "r" * 64), self.flow.calls)
        self.assertIn(("start", "j" * 32), self.flow.calls)
        self.assertEqual(self.panel._state(), "RUNNING")
        self.assertTrue(self.panel.pause_button.isVisible() or not self.panel.isVisible())
        self.flow.state = "READY_FOR_REVIEW"
        self._run(self.panel._poll_status)
        self.assertTrue(self.panel.primary.text().startswith("Ativar no projeto"))
        changed = []
        self.panel.knowledge_changed.connect(changed.append)
        dialog, name = self._confirm()
        with dialog, name:
            self._run(self.panel.primary_action)
        self.assertIn(("activate", "demo", "m" * 64), self.flow.calls)
        self.assertEqual(changed, ["demo"])
        self.assertIn("1 novo", self.panel.banner_text.text())
        self.assertIsNone(self.panel.job)
        self._run(self.panel.request_undo)
        self.assertIn(("undo", "demo"), self.flow.calls)
        self.assertIsNone(self.panel.undo_info)

    def test_partial_selection_previews_again_before_queue(self):
        self._run(lambda: self.panel.set_root("C:/pasta"))
        self.panel.selector.set_checked("docs/b.md", False)
        self.assertEqual(self.panel.primary.text(), "Indexar 1 arquivo(s)")
        dialog, name = self._confirm()
        with dialog, name:
            self._run(self.panel.primary_action)
        self.assertIn(("preview", ["src/a.py"]), self.flow.calls)
        self.assertIn(("queue", ["src/a.py"], "r" * 64), self.flow.calls)

    def test_cancelled_dialog_queues_nothing(self):
        self._run(lambda: self.panel.set_root("C:/pasta"))
        dialog, name = self._confirm(accept=False)
        with dialog, name:
            self._run(self.panel.primary_action)
        self.assertFalse([c for c in self.flow.calls if c[0] == "queue"])

    def test_public_project_is_read_only(self):
        self.panel.set_project("codebridge")
        self.panel._drain_events()
        self.assertFalse(self.panel.folder_button.isEnabled())
        self.assertFalse(self.panel.primary.isEnabled())
        self.assertIn("p\u00fablico", self.panel.footer_text.text())

    def test_cancel_job_returns_to_choose(self):
        self.flow.job = {"job_id": "k" * 32, "state": "QUEUED"}
        self.flow.state = "QUEUED"
        self.panel.set_project("demo")
        self.panel._drain_events()
        self.assertEqual(self.panel.primary.text(), "Iniciar indexa\u00e7\u00e3o")
        with patch.object(module.QMessageBox, "question", return_value=module.QMessageBox.Yes):
            self._run(self.panel.request_cancel)
        self.assertIn(("control", "CANCEL"), self.flow.calls)
        self.assertIsNone(self.panel.job)