"""Independent Windows publisher processes race; one winner, no double activation."""
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_validate import fixture
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_transition_journal import inspect_pending_transition
from rag.runtime.generation_verified_backup import verify_generation_backup

CHILD = """
import json,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[5])
from rag.runtime.generation_backup_publish import publish_with_verified_backup
root=Path(sys.argv[1])
ready=Path(sys.argv[2])
go=Path(sys.argv[3])
candidate=sys.argv[4]
ready.write_text('ready')
deadline=time.monotonic()+9
while not go.exists() and time.monotonic()<deadline:
    time.sleep(.025)
try:
    result=publish_with_verified_backup(root,'one',candidate,'backup_'+candidate)
    output={'success': True,'active':result['published']['active']}
except Exception as error:
    output={'success': False,'error':type(error).__name__}
(root/('out_'+candidate+'.json')).write_text(json.dumps(output))
"""

class ProcessPublicationRaceTests(unittest.TestCase):
    def test_two_publishers_only_one_activates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"codebridge-rag-generation-test"
            for name in ("one","two","three"):
                folder=root/"generations"/name
                folder.mkdir(parents=True)
                fixture(folder)
            activate_test_generation(root,"one")
            children=[]
            runner=getattr(sys,"_base_executable",sys.executable)
            project=str(Path(__file__).resolve().parents[1])
            try:
                for candidate in ("two","three"):
                    ready=root/("ready_"+candidate)
                    child=subprocess.Popen([runner,"-c",CHILD,str(root),str(ready),
                                             str(root/"go"),candidate,project],
                            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
                    children.append(child)
                limit=time.monotonic()+7
                while not all((root/("ready_"+name)).exists() for name in ("two","three")):
                    self.assertLess(time.monotonic(),limit,"workers not ready")
                    self.assertTrue(all(p.poll() is None for p in children),"worker exited early")
                    time.sleep(.04)
                (root/"go").touch()
                self.assertEqual([p.wait(timeout=12) for p in children],[0,0])
                results=[json.loads((root/("out_"+name+".json")).read_text())
                         for name in ("two","three")]
                self.assertEqual(sum(x["success"] for x in results),1,results)
                winning=next(x["active"] for x in results if x["success"])
                self.assertEqual(resolve_generation(root).generation,winning)
                self.assertEqual(inspect_pending_transition(root)["state"],"NO_PENDING_TRANSITION")
                self.assertEqual(verify_generation_backup(root,"backup_"+winning)["documents"],1)
            finally:
                (root/"go").touch()
                for p in children:
                    try:
                        p.wait(timeout=12)
                    except subprocess.TimeoutExpired:
                        self.fail("publisher worker did not exit")
if __name__=="__main__":
    unittest.main()
