"""RAG-AUTO-02.5: guarded process launch, Qt start, and graceful close."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

from PySide6.QtWidgets import QApplication,QMessageBox
from rag.runtime.auto_index_queue import create_draft,default_queue_path
from rag.runtime.auto_index_approval import build_auto_index_preview,approve_auto_index_draft
from rag.runtime.auto_index_launch import launch_approved_auto_job

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app_rewrite"))
from rag_auto_job_card import RagAutoJobCard


class AutoLaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt=QApplication.instance() or QApplication([])

    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base=Path(temp.name)
        self.source=self.base/"sources"
        self.source.mkdir()
        (self.source/"main.py").write_text("print(42)\n",encoding="utf-8")
        self.db=default_queue_path(self.base)
        self.project="launch-test"
        row=create_draft(
            self.db,project_id=self.project,source_root=self.source,
            idempotency_key="launch-test-12345678",allow_write=True,
        )
        self.job=row["job_id"]
        review=build_auto_index_preview(self.project,self.source)
        approve_auto_index_draft(
            self.db,self.job,review,confirmed_digest=review["review_sha256"],
            operator_approved=True,allow_write=True,
        )

    def test_no_implicit_subprocess(self):
        with patch("rag.runtime.auto_index_launch.subprocess.Popen") as start:
            with self.assertRaises(PermissionError):
                launch_approved_auto_job(self.db,self.job)
        start.assert_not_called()

    def test_launch_uses_fixed_argv_sanitized_env_and_local_log(self):
        def fake_spawn(argv,**kwargs):
            self.assertEqual(argv[:4],[str(Path(sys.executable).resolve()),"-u","-m",
                                         "rag.runtime.auto_index_runner"])
            self.assertIn("--job-id",argv)
            self.assertNotIn("shell",kwargs)
            self.assertEqual(kwargs["stdin"],__import__("subprocess").DEVNULL)
            self.assertEqual(kwargs["env"]["PYTHONDONTWRITEBYTECODE"],"1")
            self.assertNotIn("CONTROL_PLANE_API_KEY",kwargs["env"])
            self.assertTrue(Path(kwargs["cwd"]).is_dir())
            return Mock(pid=24680)
        with patch("rag.runtime.auto_index_launch._free_ram_mib",return_value=4096):
            result=launch_approved_auto_job(
                self.db,self.job,execute=True,operator_approved=True,
                confirmation="RAG_AUTO_LAUNCH:"+self.job,
                python_executable=Path(sys.executable),popen_factory=fake_spawn,
            )
        self.assertEqual(result["state"],"PROCESS_STARTED_UNVERIFIED")
        self.assertEqual(result["pid"],24680)
        self.assertTrue(Path(result["log_path"]).is_file())
        self.assertFalse(result["index_published"])

    def test_low_memory_blocks_launch(self):
        with patch("rag.runtime.auto_index_launch._free_ram_mib",return_value=800):
            result=launch_approved_auto_job(
                self.db,self.job,execute=True,operator_approved=True,
                confirmation="RAG_AUTO_LAUNCH:"+self.job,
            )
        self.assertEqual(result["state"],"WAITING_FOR_MEMORY")
        self.assertFalse(result["process_started"])

    def test_visual_start_requires_human_confirmation(self):
        card=RagAutoJobCard(queue_path=self.db,project_id=self.project)
        self.addCleanup(card.close)
        self.assertTrue(card.start_button.isEnabled())
        with (patch.object(QMessageBox,"question",return_value=QMessageBox.No),
              patch("rag.runtime.auto_index_launch.launch_approved_auto_job") as launch):
            card.start_button.click()
        launch.assert_not_called()
        with (patch.object(QMessageBox,"question",return_value=QMessageBox.Yes),
              patch("rag.runtime.auto_index_launch.launch_approved_auto_job",
                    return_value={"state":"PROCESS_STARTED_UNVERIFIED","pid":111}) as launch):
            card.start_button.click()
        launch.assert_called_once()
        self.assertIn("PID 111",card.detail.text())


if __name__=="__main__":
    unittest.main()
