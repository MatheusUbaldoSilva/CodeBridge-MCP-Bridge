"""Conservative lab family-exit observations. Never authorizes production backup."""
from __future__ import annotations
from rag.runtime.offline_process_family_audit import audit_known_family


def inspect_family_shutdown_samples(root_pid, snapshots):
    result={"state":"BLOCKED","observed_family_pids":[],
            "issues":[],"copy_authorized":False,
            "all_handles_closed":False,"production_quiescence_proven":False}
    try:
        if not isinstance(snapshots,list) or len(snapshots)<3:
            raise ValueError("need active and two absent samples")
        first=snapshots[0]
        starting=audit_known_family(root_pid,first)
        if starting["state"]!="KNOWN_FAMILY_OBSERVED_UNPROVEN":
            raise ValueError("root never observed")
        baseline=set(starting["known_descendant_pids"]) | {root_pid}
        last_active=set(baseline)
        consecutive_absences=0
        for snap in snapshots:
            if (not isinstance(snap,dict) or
                    snap.get("identity_inventory_ok") is not True or
                    snap.get("unverified_count")!=0 or
                    not isinstance(snap.get("verified_pids"),list)):
                result["issues"].append("UNTRUSTED_PROCESS_INVENTORY")
                break
            records=snap["verified_pids"]
            ids={item.get("pid") for item in records if isinstance(item,dict)}
            if len(ids)!=len(records):
                raise ValueError("duplicate PID")
            new_children={item["pid"] for item in records
                          if isinstance(item,dict)
                          and item.get("parent_pid") in last_active
                          and item.get("pid") not in baseline}
            if new_children:
                result["issues"].append("LATE_CHILD_OBSERVED")
                break
            active=ids & baseline
            if active:
                last_active=active
                consecutive_absences=0
            else:
                consecutive_absences+=1
            if consecutive_absences>=2:
                result["state"]="LAB_FAMILY_ABSENT_UNPROVEN"
                result["observed_family_pids"]=sorted(baseline)
                break
        else:
            result["issues"].append("INSUFFICIENT_ABSENCE_EVIDENCE")
    except (OSError,TypeError,ValueError,KeyError) as exc:
        result["issues"]=[type(exc).__name__]
    return result
