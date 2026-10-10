import tempfile,unittest
from pathlib import Path
from benchmarks.stage_rag017_install_package import stage

class RagStagingTests(unittest.TestCase):
 def test_stages_without_touching_installed(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); source=root/"source"
   (source/"rag").mkdir(parents=True); (source/"author_mcp").mkdir(); (source/"installer").mkdir()
   (source/"rag"/"__init__.py").write_text("")
   (source/"rag"/"module.py").write_text("FLAG=True")
   (source/"author_mcp"/"mcp_server.py").write_text("pass")
   (source/"installer"/"bootstrap.ps1").write_text("pass")
   dest=root/"stage"
   report=stage(source,dest)
   self.assertTrue(report["staged"])
   self.assertFalse(report["installed"])
   self.assertFalse(report["production_approved"])
   self.assertTrue((dest/"rag"/"module.py").is_file())
   with self.assertRaises(FileExistsError):stage(source,dest)
 def test_missing_rag_package_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   with self.assertRaises(FileNotFoundError):stage(root,root/"stage")
