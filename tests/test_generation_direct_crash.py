"""Independent Windows reader processes and abnormal exit regression."""
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.generation_process_lock import generation_lock, GenerationBusy

CHILD_SCRIPT = """
import os,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[4])
from rag.runtime.generation_process_lock import generation_lock
with generation_lock(Path(sys.argv[1]), 'one'):
    Path(sys.argv[2]).write_text('ready')
    deadline=time.monotonic()+8
    while not Path(sys.argv[3]).exists() and time.monotonic()<deadline:
        time.sleep(.025)
    if sys.argv[5]=='abrupt':
        os._exit(37)
"""

def wait_ready(marker, proc):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        if marker.exists():
            return
        if proc.poll() is not None:
            raise AssertionError("child exited before ready")
        time.sleep(.03)
    raise AssertionError("child readiness timeout")

class DirectReaderCrashTests(unittest.TestCase):
    def test_abrupt_exit_preserves_remaining_reader_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"codebridge-rag-generation-test"
            root.mkdir()
            runner=getattr(sys,"_base_executable",sys.executable)
            children=[]
            try:
                for i,mode in enumerate(("abrupt","normal")):
                    marker=root/("ready"+str(i))
                    release=root/("release"+str(i))
                    child=subprocess.Popen([runner,"-c",CHILD_SCRIPT,str(root),str(marker),
                        str(release),str(Path(__file__).resolve().parents[1]),mode],
                        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    children.append(child)
                    wait_ready(marker,child)
                with self.assertRaises(GenerationBusy):
                    with generation_lock(root,"one",exclusive=True):
                        pass
                (root/"release0").touch()
                self.assertEqual(children[0].wait(timeout=4),37)
                self.assertIsNone(children[1].poll())
                with self.assertRaises(GenerationBusy):
                    with generation_lock(root,"one",exclusive=True):
                        pass
                (root/"release1").touch()
                self.assertEqual(children[1].wait(timeout=4),0)
                with generation_lock(root,"one",exclusive=True):
                    pass
            finally:
                for i in range(2):
                    (root/("release"+str(i))).touch()
                for child in children:
                    try:
                        child.wait(timeout=9)
                    except subprocess.TimeoutExpired:
                        self.fail("isolated child did not stop after release")
if __name__=="__main__":
    unittest.main()
