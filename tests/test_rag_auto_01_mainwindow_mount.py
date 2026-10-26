"""RAG-AUTO-01 GUI acceptance: mount the new card in CodeBridge MainWindow."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock,patch

from PySide6.QtWidgets import QApplication,QWidget

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"app_rewrite"))

from ui import MainWindow
import ui


class MainWindowRagAutoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt=QApplication.instance() or QApplication([])

    def test_main_window_mounts_auto_tab_without_real_services(self):
        runtime=MagicMock()
        runtime.auto_execute=False
        runtime.completion_sound.enabled=False
        runtime.terminals.ssh_settings.return_value={}
        with (
            patch.object(ui,"TelemetryService") as service,
            patch.object(ui,"TelemetryPanel",side_effect=lambda *args:QWidget()),
            patch.object(ui,"TerminalWidget",
                         side_effect=lambda terminals,target,parent:QWidget(parent)),
            patch.object(MainWindow,"refresh",return_value=None),
            patch.object(MainWindow,"refresh_telemetry",return_value=None),
            patch.object(MainWindow,"_load_ssh_settings",return_value=None),
        ):
            main=MainWindow(runtime)
            try:
                self.assertGreaterEqual(main.tabs.count(),5)
                self.assertEqual(main.tabs.tabText(main.tabs.indexOf(main.rag_tab)),"Central RAG")
                self.assertEqual(main.rag_tab.pages.count(),4)
                self.assertEqual(
                    main.rag_tab.nav_buttons[3].text(),
                    "Indexação automática"
                )
                self.assertIsNotNone(main.rag_tab.auto_card)
                self.assertFalse(main.rag_tab.auto_card.pause_button.isEnabled())
                service.return_value.start.assert_called_once()
            finally:
                main.close()
                service.return_value.stop.assert_called_once()


if __name__=="__main__":
    unittest.main()
