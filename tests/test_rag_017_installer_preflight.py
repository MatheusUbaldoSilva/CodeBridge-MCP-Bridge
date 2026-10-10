import tempfile,unittest
from pathlib import Path
from benchmarks.rag017_installer_preflight import check

class InstallerPreflightTests(unittest.TestCase):
 def setup_tree(self,root,with_rag):
  src=root/"source"; ins=root/"installed"
  (src/"installer").mkdir(parents=True)
  (src/"author_mcp").mkdir()
  (ins/"author_mcp").mkdir(parents=True)
  (src/"author_mcp"/"mcp_server.py").write_text('name="codebridge_rag_status"')
  (ins/"author_mcp"/"mcp_server.py").write_text("old version")
  lines=['SetOutPath "$INSTDIR\\author_mcp"']
  if with_rag:lines.extend(['SetOutPath "$INSTDIR\\rag"','File /r "..\\rag\\*"'])
  (src/"installer"/"CodeBridge.nsi").write_text("\n".join(lines))
  return src,ins
 def test_current_package_must_fail_closed_without_rag(self):
  with tempfile.TemporaryDirectory() as d:
   src,ins=self.setup_tree(Path(d),False)
   self.assertFalse(check(src/"installer"/"CodeBridge.nsi",src,ins)["safe_to_update_rag"])
 def test_packaged_rag_candidate_can_pass_structural_check(self):
  with tempfile.TemporaryDirectory() as d:
   src,ins=self.setup_tree(Path(d),True)
   self.assertTrue(check(src/"installer"/"CodeBridge.nsi",src,ins)["safe_to_update_rag"])
