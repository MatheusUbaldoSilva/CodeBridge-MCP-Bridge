import sys,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_process_lineage_evidence import assess_scoped_family_timeline

T=datetime(2026,10,17,12,tzinfo=timezone.utc)
OLD="/Date(1600000000000)/"
YOUNG="/Date(1600000001000)/"
def person(pid,parent,born):
    return {"pid":pid,"parent_pid":parent,"created_at":born,
            "executable_fingerprint":"a"*64}
def frame(i,rows,scope=None):
    at=T+timedelta(seconds=i)
    return {"source":"WINDOWS_CIM_LAB_SCOPED",
            "identity_inventory_ok":True,"unverified_count":0,
            "verified_pids":rows,"scope_pids":[10,11] if scope is None else scope,
            "observed_start_utc":at.isoformat(),
            "observed_end_utc":(at+timedelta(milliseconds=1)).isoformat()}
def basic():
    parent=person(10,0,OLD);child=person(11,10,YOUNG)
    return [frame(0,[parent,child]),frame(1,[child]),frame(2,[]),frame(3,[])]
class FamilyLineageTests(unittest.TestCase):
    def test_real_cim_msdate_family_exits_non_authorizing(self):
        result=assess_scoped_family_timeline(10,basic())
        self.assertEqual(result["state"],"LAB_TEMPORAL_FAMILY_EXIT_UNPROVEN_FOR_PRODUCTION")
        self.assertEqual(result["known_family_pids"],[10,11])
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["all_handles_closed"])
    def test_child_older_than_parent_blocks(self):
        data=basic();data[0]["verified_pids"][1]["created_at"]="/Date(1599999999000)/"
        self.assertIn("CHILD_PREDATES_PARENT",assess_scoped_family_timeline(10,data)["issues"])
    def test_parent_identity_changes_blocks(self):
        data=basic();data[0]["verified_pids"][0]["executable_fingerprint"]="b"*64
        data.insert(1,frame(1,[person(10,0,OLD),person(11,10,YOUNG)]))
        for i,item in enumerate(data):
            at=T+timedelta(seconds=i)
            item["observed_start_utc"]=at.isoformat()
            item["observed_end_utc"]=(at+timedelta(milliseconds=1)).isoformat()
        self.assertIn("PID_REUSED_OR_IDENTITY_CHANGED",
                      assess_scoped_family_timeline(10,data)["issues"])
    def test_root_missing_blocks(self):
        data=basic();data[0]["verified_pids"]=[person(11,10,YOUNG)]
        self.assertIn("ROOT_NOT_OBSERVED",assess_scoped_family_timeline(10,data)["issues"])
    def test_untracked_parent_blocks(self):
        data=basic();data[0]["verified_pids"][1]["parent_pid"]=999
        self.assertIn("UNVERIFIED_PARENT_IN_BASELINE",
                      assess_scoped_family_timeline(10,data)["issues"])
    def test_broken_clock_blocks(self):
        data=basic();data[1]["observed_start_utc"]=data[0]["observed_start_utc"]
        self.assertIn("INVALID_TIMED_SAMPLE_SERIES",
                      assess_scoped_family_timeline(10,data)["issues"])
    def test_process_late_birth_blocks(self):
        data=basic();data[0]["verified_pids"][0]["created_at"]="2090-01-01T00:00:00+00:00"
        self.assertIn("PROCESS_BORN_AFTER_OBSERVATION",
                      assess_scoped_family_timeline(10,data)["issues"])
    def test_unknown_birth_format_blocks(self):
        data=basic();data[0]["verified_pids"][0]["created_at"]="not-a-time"
        self.assertEqual(assess_scoped_family_timeline(10,data)["state"],"BLOCKED")
if __name__=="__main__": unittest.main()
