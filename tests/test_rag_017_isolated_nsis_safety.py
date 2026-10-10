"""Fail if isolated NSIS recipe acquires app/registry/process side effects."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NSIS=ROOT/"installer"/"RAG017_Isolated_Test.nsi"
class IsolatedInstallerSafetyTests(unittest.TestCase):
 def test_isolation_script_contains_no_mutating_side_effects(self):
  text=NSIS.read_text(encoding="utf-8-sig").lower()
  for token in ("writereg","deletereg","createshortcut","execwait","nsexec::","exec '","writeuninstaller","rm dir","rmdir","!include"):
   self.assertNotIn(token,text,token)
 def test_only_expected_test_payload(self):
  text=NSIS.read_text(encoding="utf-8-sig")
  self.assertIn('File /r "..\\rag\\*.py"',text)
  self.assertIn('File "..\\author_mcp\\mcp_server.py"',text)
  self.assertIn('RequestExecutionLevel user',text)
  self.assertIn('SilentInstall silent',text)
