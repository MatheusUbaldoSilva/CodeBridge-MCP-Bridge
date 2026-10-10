import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=(ROOT/"benchmarks"/"rag017_isolated_embedded_probe.py").read_text(encoding="utf-8")
class EmbeddedProbeContractTests(unittest.TestCase):
 def test_probe_requires_native_dependencies(self):
  self.assertIn('"numpy"',SCRIPT)
  self.assertIn('"qdrant_client"',SCRIPT)
  self.assertIn('all(available.values())',SCRIPT)
 def test_probe_adds_only_process_local_import_path(self):
  self.assertIn('sys.path.insert(0,str(a.payload.resolve()))',SCRIPT)
  self.assertNotIn('os.environ[',SCRIPT)
  self.assertNotIn('pip install',SCRIPT)
