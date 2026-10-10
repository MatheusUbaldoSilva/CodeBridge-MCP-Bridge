import tempfile,unittest
from pathlib import Path
from benchmarks.rag017_nsis_build_gate import check

class NSISBuildGateTests(unittest.TestCase):
 def create(self,root):
  for name in ("installer/CodeBridge.nsi","installer/bootstrap.ps1","author_mcp/mcp_server.py","rag/__init__.py"):
   f=root/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text("test")
 def test_missing_compiler_fails(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.create(root)
   result=check(root,compiler=root/"not-found.exe")
   self.assertFalse(result["compile_preflight_passed"])
   self.assertFalse(result["compilation_verified"])
 def test_old_executable_not_accepted_as_new_build(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.create(root)
   dest=root/"installer/dist/CodeBridge-Setup.exe";dest.parent.mkdir(parents=True);dest.write_bytes(b"old")
   import os
   os.utime(dest,(1,1))
   result=check(root,compiler=root/"not-found.exe")
   self.assertFalse(result["installer_newer_than_inputs"])
   self.assertFalse(result["installation_verified"])
   self.assertFalse(result["rollback_verified"])
