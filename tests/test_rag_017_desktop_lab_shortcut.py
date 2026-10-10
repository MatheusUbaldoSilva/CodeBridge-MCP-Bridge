import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=(ROOT/"benchmarks"/"CodeBridge_MCP_RAG_Lab.ps1").read_text(encoding="utf-8")
class RAGDesktopLabTests(unittest.TestCase):
 def test_is_read_only_and_explicitly_experimental(self):
  for required in ("LABORATORIO EXPERIMENTAL","rag017_isolated_embedded_probe.py","rag017_qdrant_isolated_persistence.py","RAG-017-J BLOQUEADO"):
   self.assertIn(required,SCRIPT)
  for forbidden in ("Start-Process","Stop-Process","pip install","git checkout","git reset","Set-ItemProperty","New-ItemProperty"):
   self.assertNotIn(forbidden,SCRIPT)
 def test_missing_temporary_runtime_fails_closed(self):
  self.assertIn("Ambiente temporario ausente.",SCRIPT)
  self.assertIn("exit 2",SCRIPT)
