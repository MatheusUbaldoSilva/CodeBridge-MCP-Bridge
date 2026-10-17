import subprocess,sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_process_family_supervisor import inspect_family_shutdown_samples
from rag.runtime.offline_scoped_cim_observer import observe_scoped_windows_pids
from rag.runtime.offline_process_sample_contract import validate_observation_series
from rag.runtime.offline_process_sampling_gate import evaluate_scoped_exit_window
from datetime import datetime, timezone
from rag.runtime.offline_process_lineage_evidence import assess_scoped_family_timeline
from rag.runtime.offline_store_handle_probe import inspect_fixture_handles
from rag.runtime.offline_fixture_file_guard import hold_fixture_files_readonly, FixtureFileBusy
from test_incremental_bundle_e2e import create_bundle
CHILD="""import mmap,pathlib,sys,time
p=pathlib.Path(sys.argv[1])
f=open(sys.argv[2],'r+b',buffering=0)
manifest=open(sys.argv[3],'rb')
reader=mmap.mmap(manifest.fileno(),0,access=mmap.ACCESS_READ)
manifest.close()
vector=open(sys.argv[4],'r+b',buffering=0)
end=time.monotonic()+15
while not p.exists() and time.monotonic()<end: time.sleep(.05)
reader.close()
vector.close()
f.close()
sys.exit(0 if p.exists() else 2)
"""
PARENT="""import subprocess,sys
p=subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5]],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print(p.pid,flush=True)
sys.exit(0 if sys.stdin.readline().strip()=='STOP' else 3)
"""
def snapshot(pids):
    report = observe_scoped_windows_pids(list(pids))
    if report["state"] != "SCOPED_CIM_OBSERVATION_UNPROVEN":
        raise ValueError("scoped Windows observation blocked")
    return report

@unittest.skipUnless(sys.platform=='win32','Windows-only test')
class ScopedFamily(unittest.TestCase):
 def test_cooperative_parent_then_child_exit(self):
    with tempfile.TemporaryDirectory(prefix='rag-lab-') as d:
        stop=Path(d)/'stop'
        root=Path(d)/'codebridge-rag-generation-test'
        create_bundle(root,[('lab','entry','synthetic')])
        database=root/'rag_index.sqlite3'
        vector=next(p for p in (root/'qdrant').rglob('*') if p.is_file())
        parent=subprocess.Popen([sys.executable,'-c',PARENT,CHILD,str(stop),str(database),str(root/'rag-index-manifest.json'),str(vector)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            child=int(parent.stdout.readline().strip());pids=(parent.pid,child)
            first=snapshot(pids)
            self.assertEqual({x['pid'] for x in first['verified_pids']},set(pids))
            parent.stdin.write('STOP\n');parent.stdin.flush()
            self.assertEqual(parent.wait(timeout=8),0)
            middle=snapshot(pids)
            self.assertEqual({x['pid'] for x in middle['verified_pids']},{child})
            still_open=inspect_family_shutdown_samples(parent.pid,[first,middle,middle])
            self.assertEqual(still_open['state'],'BLOCKED')
            self.assertFalse(still_open['copy_authorized'])
            active=inspect_fixture_handles(root)
            self.assertEqual(active['state'],'BLOCKED')
            self.assertFalse(active['copy_authorized'])
            self.assertFalse(active['all_handles_closed'])
            with self.assertRaises(FixtureFileBusy):
                with hold_fixture_files_readonly([vector]): pass
            stop.touch()
            for _ in range(30):
                last=snapshot(pids)
                if not last['verified_pids']: break
                time.sleep(.1)
            else: self.fail('synthetic child remains')
            final = snapshot(pids)
            clock_report = validate_observation_series([first, middle, last, final])
            self.assertEqual(clock_report["state"], "TIMED_LAB_OBSERVATIONS_VALID_UNPROVEN")
            lineage = assess_scoped_family_timeline(parent.pid, [first, middle, last, final])
            self.assertEqual(lineage["state"], "LAB_TEMPORAL_FAMILY_EXIT_UNPROVEN_FOR_PRODUCTION")
            self.assertFalse(lineage["copy_authorized"])
            self.assertFalse(clock_report["production_quiescence_proven"])
            window = evaluate_scoped_exit_window(
                [first, middle, last, final],
                now=datetime.now(timezone.utc), max_gap_ms=7000,
                max_age_ms=15000)
            self.assertEqual(window["state"], "LAB_SCOPED_EXIT_WINDOW_UNPROVEN")
            self.assertFalse(window["copy_authorized"])
            self.assertFalse(window["all_handles_closed"])
            result=inspect_family_shutdown_samples(parent.pid,[first,middle,last,final])
            self.assertEqual(result['state'],'LAB_FAMILY_ABSENT_UNPROVEN')
            released=inspect_fixture_handles(root)
            self.assertEqual(released['state'],'LAB_HANDLES_READABLE_UNPROVEN')
            self.assertFalse(released['copy_authorized'])
            self.assertFalse(released['production_quiescence_proven'])
            self.assertFalse(result['copy_authorized'])
        finally:
            stop.touch()
            if parent.poll() is None:
                parent.stdin.write('STOP\n');parent.stdin.flush();parent.wait(timeout=8)
            parent.stdin.close();parent.stdout.close();parent.stderr.close()
