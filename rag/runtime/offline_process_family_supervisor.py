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
        original_ids = {item["pid"]: (item.get("created_at"),
                          item.get("executable_fingerprint")) for item in first["verified_pids"]
                          if item["pid"] in baseline}
        last_active=set(baseline)
        was_absent=set()
        consecutive_absences=0
        for snap in snapshots:
            if (not isinstance(snap,dict) or
                    snap.get("identity_inventory_ok") is not True or
                    snap.get("unverified_count")!=0 or
                    not isinstance(snap.get("verified_pids"),list)):
                result["issues"].append("UNTRUSTED_PROCESS_INVENTORY")
                break
            records=snap["verified_pids"]
            ids=set()
            for item in records:
                if not isinstance(item,dict):
                    raise ValueError("invalid process row")
                pid=item.get("pid")
                parent=item.get("parent_pid")
                born=item.get("created_at")
                exe=item.get("executable_fingerprint")
                if (not isinstance(pid,int) or isinstance(pid,bool) or pid<=0 or
                    not isinstance(parent,int) or isinstance(parent,bool) or parent<0 or
                    not isinstance(born,str) or not born or
                    not isinstance(exe,str) or len(exe)!=64 or
                    any(c not in "0123456789abcdef" for c in exe) or pid in ids):
                    raise ValueError("untrusted process identity")
                ids.add(pid)
            new_children={item["pid"] for item in records
                          if isinstance(item,dict)
                          and item.get("parent_pid") in baseline
                          and item.get("pid") not in baseline}
            if new_children:
                result["issues"].append("LATE_CHILD_OBSERVED")
                break
            for item in records:
                if item["pid"] in original_ids and (
                     item.get("created_at"), item.get("executable_fingerprint")
                     ) != original_ids[item["pid"]]:
                    result["issues"].append("FAMILY_PID_IDENTITY_CHANGED")
                    return result
            active=ids & baseline
            if active & was_absent:
                result["issues"].append("FAMILY_PROCESS_REAPPEARED")
                break
            was_absent.update(baseline - active)
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
