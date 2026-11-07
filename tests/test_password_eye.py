"""Olhinho do campo de senha SSH."""
import os
import sys
import unittest
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_rewrite"))
from PySide6.QtWidgets import QApplication, QLineEdit
from password_eye import PasswordEye


class PasswordEyeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_toggle_typed_password(self):
        edit = QLineEdit()
        eye = PasswordEye(edit, lambda: "salva")
        edit.setText("digitada")
        self.assertEqual(edit.echoMode(), QLineEdit.Password)
        eye.toggle()
        self.assertEqual(edit.echoMode(), QLineEdit.Normal)
        self.assertEqual(edit.text(), "digitada")
        eye.toggle()
        self.assertEqual(edit.echoMode(), QLineEdit.Password)

    def test_empty_field_shows_saved_password(self):
        edit = QLineEdit()
        eye = PasswordEye(edit, lambda: "salva")
        eye.toggle()
        self.assertEqual((edit.text(), eye.visible), ("salva", True))

    def test_no_saved_password(self):
        edit = QLineEdit()
        eye = PasswordEye(edit, lambda: (_ for _ in ()).throw(RuntimeError("x")))
        eye.toggle()
        self.assertEqual(edit.text(), "")
        self.assertTrue(eye.visible)


if __name__ == "__main__":
    unittest.main()