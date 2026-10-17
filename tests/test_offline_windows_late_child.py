"""Windows synthetic late-child race; this is never a production shutdown proof."""
import subprocess,sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from test_offline_windows_scoped_family import snapshot,CHILD
from rag.runtime.offline_process_family_supervisor import inspect_family_shutdown_samples
PARENT_LATE="""import subprocess,sys
if sys.stdin.readline().strip()!='SPAWN':sys.exit(3)
p=subprocess.Popen([sys.executable,'-c',sys.argv[1],*sys.argv[2:]],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print(p.pid,flush=True)
sys.exit(0 if sys.stdin.readline().strip()=='STOP' else 4)
"""
@unittest.skipUnless(sys.platform=="win32","Windows-only scoped process test")
class LateSyntheticChild(unittest.TestCase):
 def test_late_spawn_is_rejected(self):
    with tempfile.TemporaryDirectory(prefix="rag-lab-late-") as folder:
        root=Path(folder)/"codebridge-rag-generation-test"
        create_bundle(root,[("lab","note","synthetic")])
        stop=Path(folder)/"child-stop"
        vec=next(p for p in (root/"qdrant").rglob("*") if p.is_file())
        parent=subprocess.Popen([sys.executable,"-c",PARENT_LATE,CHILD,str(stop),
            str(root/"rag_index.sqlite3"),str(root/"rag-index-manifest.json"),str(vec)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        child=None
        try:
            first=snapshot((parent.pid,))
            self.assertEqual({r["pid"] for r in first["verified_pids"]},{parent.pid})
            parent.stdin.write("SPAWN\n");parent.stdin.flush()
            child=int(parent.stdout.readline().strip())
            second=snapshot((parent.pid,child))
            self.assertEqual({r["pid"] for r in second["verified_pids"]},{parent.pid,child})
            self.assertEqual(next(r["parent_pid"] for r in second["verified_pids"] if r["pid"]==child),parent.pid)
            report=inspect_family_shutdown_samples(parent.pid,[first,second,second])
            self.assertIn("LATE_CHILD_OBSERVED",report["issues"])
            self.assertFalse(report["copy_authorized"])
            parent.stdin.write("STOP\n");parent.stdin.flush()
            self.assertEqual(parent.wait(timeout=8),0)
        finally:
            stop.touch()
            if parent.poll() is None:
                parent.stdin.write("STOP\n");parent.stdin.flush();parent.wait(timeout=8)
            parent.stdin.close();parent.stdout.close();parent.stderr.close()
            if child:
                for _ in range(40):
                    if not snapshot((child,))["verified_pids"]:break
                    time.sleep(.1)
