import json,os,tempfile,unittest
from pathlib import Path
from installer.rag_p9b_detached_recovery_gate import verify_boundary

class BoundaryTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
  self.root=Path(self.t.name);self.mark=self.root/'marker.json';self.journal=self.root/'journal.jsonl'
  self.mark.write_text(json.dumps({'purpose':'P9B_DISPOSABLE_UNIFIED_LAB','lab':str(self.root.resolve())}))
  self.journal.write_text(json.dumps({'state':'SHELL_NSIS_LAB_INTERRUPTED'})+'\n')
 def check(self,**kwargs):
  options=dict(marker=self.mark,journal=self.journal,installer_pid=998877,
               supervisor_pid=os.getpid(),lab=self.root);options.update(kwargs)
  return verify_boundary(**options)
 def test_valid_boundary(self):
  self.assertTrue(self.check()['verified'])
 def test_wrong_process(self):
  self.assertEqual(self.check(supervisor_pid=1)['reason'],'SUPERVISOR_PID_NOT_ATTESTED')
 def test_missing_lab_marker(self):
  self.mark.write_text('{}')
  self.assertEqual(self.check()['reason'],'LAB_IDENTITY_INVALID')
 def test_missing_interruption(self):
  self.journal.write_text('{}\n')
  self.assertEqual(self.check()['reason'],'INTERRUPTION_UNVERIFIED')
if __name__=='__main__':unittest.main()
