"""Read-only laboratory observation of a known process family.

A parent-child relationship alone is not proof of provenance or full quiescence.
Never stop any process; never authorize an offline production copy.
"""
from __future__ import annotations


def audit_known_family(root_pid, snapshot):
    report = {"state": "BLOCKED", "known_descendant_pids": [],
              "unresolved_parent_pids": [], "copy_authorized": False,
              "all_processes_known": False, "all_handles_closed": False,
              "production_quiescence_proven": False}
    try:
        if not isinstance(root_pid, int) or isinstance(root_pid, bool) or root_pid <= 0:
            raise ValueError("invalid root PID")
        if (not isinstance(snapshot, dict) or
                snapshot.get("identity_inventory_ok") is not True or
                snapshot.get("unverified_count") != 0 or
                not isinstance(snapshot.get("verified_pids"), list)):
            raise ValueError("untrusted inventory")
        rows = {}
        for item in snapshot["verified_pids"]:
            if not isinstance(item, dict):
                raise ValueError("invalid row")
            pid = item.get("pid")
            if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0 or pid in rows:
                raise ValueError("invalid or duplicate PID")
            parent = item.get("parent_pid")
            if parent is not None and (not isinstance(parent, int) or isinstance(parent, bool) or parent < 0 or parent == pid):
                raise ValueError("invalid parent")
            if not item.get("created_at") or not item.get("executable_fingerprint"):
                raise ValueError("missing identity")
            rows[pid] = item
        if root_pid not in rows:
            raise ValueError("root identity not in inventory")
        # Cycles in observed parent relationships indicate corrupted/reused identities.
        for pid in rows:
            checked = set()
            current = pid
            while current in rows:
                if current in checked:
                    raise ValueError("cyclic parent relationship")
                checked.add(current)
                parent = rows[current].get("parent_pid")
                if parent in (None, 0):
                    break
                current = parent
        descendants = set()
        frontier = {root_pid}
        while frontier:
            following = {pid for pid, item in rows.items()
                         if item.get("parent_pid") in frontier and pid not in descendants
                         and pid != root_pid}
            descendants.update(following)
            frontier = following
        report["known_descendant_pids"] = sorted(descendants)
        report["unresolved_parent_pids"] = sorted({
            row["parent_pid"] for row in rows.values()
            if row.get("parent_pid") not in (None, 0) and
            row["parent_pid"] not in rows
        })
        report["state"] = "KNOWN_FAMILY_OBSERVED_UNPROVEN"
    except (TypeError, ValueError, KeyError) as exc:
        report["error_type"] = type(exc).__name__
    return report
