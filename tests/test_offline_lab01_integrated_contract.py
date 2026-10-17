"""RAG-LAB.01 contract integration: CIM -> timed observations -> lineage -> exit."""
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_scoped_cim_observer import observe_scoped_windows_pids
from rag.runtime.offline_process_sample_contract import validate_observation_series
from rag.runtime.offline_process_lineage_evidence import assess_scoped_family_timeline
from rag.runtime.offline_process_sampling_gate import evaluate_scoped_exit_window

BASE = datetime(2026, 10, 17, 14, tzinfo=timezone.utc)
def row(pid, parent):
    return {"ProcessId":pid,"ParentProcessId":parent,
            "CreationDate":"/Date(%s)/"%(1600000000000+(pid-100)*1000),
            "ExecutablePath":"C:/synthetic/python.exe"}

def collect(rows_per_sample):
    count=[0]
    times=iter([BASE+timedelta(seconds=i,milliseconds=offset)
                for i in range(len(rows_per_sample)) for offset in (0,50)])
    def runner(*args,**kwargs):
        index=count[0];count[0]+=1
        return SimpleNamespace(stdout=json.dumps(rows_per_sample[index]))
    return [observe_scoped_windows_pids([100,101],runner=runner,
            clock=lambda: next(times)) for _ in rows_per_sample]

class Lab01IntegrationTests(unittest.TestCase):
    def test_positive_known_family_remains_non_authorizing(self):
        observations=collect([[row(100,0),row(101,100)],
                              [row(101,100)],[],[]])
        self.assertTrue(all(x["identity_inventory_ok"] for x in observations))
        self.assertEqual(validate_observation_series(observations)["state"],
                         "TIMED_LAB_OBSERVATIONS_VALID_UNPROVEN")
        family=assess_scoped_family_timeline(100,observations)
        self.assertEqual(family["state"],
                         "LAB_TEMPORAL_FAMILY_EXIT_UNPROVEN_FOR_PRODUCTION")
        window=evaluate_scoped_exit_window(
            observations,now=BASE+timedelta(seconds=3,milliseconds=100))
        self.assertEqual(window["state"],"LAB_SCOPED_EXIT_WINDOW_UNPROVEN")
        self.assertFalse(window["copy_authorized"])
        self.assertFalse(family["production_quiescence_proven"])
    def test_late_child_is_rejected_through_chain(self):
        observations=collect([[row(100,0)],[row(100,0),row(101,100)],[],[]])
        family=assess_scoped_family_timeline(100,observations)
        window=evaluate_scoped_exit_window(
            observations,now=BASE+timedelta(seconds=3,milliseconds=100))
        self.assertEqual(family["state"],"BLOCKED")
        self.assertEqual(window["state"],"BLOCKED")
    def test_partial_cim_response_blocks_all_evidence(self):
        invalid=dict(row(101,100),ExecutablePath=None)
        observations=collect([[row(100,0),invalid],[row(101,100)],[],[]])
        self.assertEqual(observations[0]["state"],"BLOCKED")
        self.assertEqual(observations[0]["verified_pids"],[])
        self.assertEqual(validate_observation_series(observations)["state"],"BLOCKED")
        self.assertEqual(assess_scoped_family_timeline(100,observations)["state"],"BLOCKED")
        self.assertEqual(evaluate_scoped_exit_window(
            observations,now=BASE+timedelta(seconds=3,milliseconds=100))["state"],
            "BLOCKED")

if __name__ == "__main__":
    unittest.main()
