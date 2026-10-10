"""Fail-closed comparison of pre/post rollback evidence from a disposable VM.

A comparison can detect differences, but cannot prove that the hypervisor snapshot
was actually restored. That remains independent external evidence.
"""
import argparse
import json
from pathlib import Path

SECTIONS = ("files", "registry", "shortcuts", "services")
FLAGS = ("registry_snapshot_verified", "shortcuts_snapshot_verified",
         "services_snapshot_verified", "vm_snapshot_verified")


def compare(before, after):
    changes = {}
    for section in SECTIONS:
        left = before.get(section)
        right = after.get(section)
        if not isinstance(left, dict) or not isinstance(right, dict):
            changes[section] = {"available": False, "added": [], "removed": [], "modified": []}
            continue
        a, b = set(left), set(right)
        changes[section] = {
            "available": True,
            "added": sorted(b - a),
            "removed": sorted(a - b),
            "modified": sorted(k for k in (a & b) if left[k] != right[k]),
        }
    vm_same = isinstance(before.get("vm_id"), str) and bool(before["vm_id"].strip()) and before["vm_id"] == after.get("vm_id")
    same_root = isinstance(before.get("root"), str) and bool(before["root"].strip()) and before["root"] == after.get("root")
    evidence_complete = vm_same and same_root and all(
        before.get(flag) is True and after.get(flag) is True for flag in FLAGS
    ) and all(changes[s]["available"] for s in SECTIONS)
    difference_found = any(
        changes[s]["added"] or changes[s]["removed"] or changes[s]["modified"]
        for s in SECTIONS
    )
    return {
        "same_vm_identity": vm_same,
        "same_evidence_root": same_root,
        "evidence_complete": evidence_complete,
        "differences": changes,
        "differences_found": difference_found,
        "comparison_passed": evidence_complete and not difference_found,
        "rollback_full_verified": False,
        "host_execution_allowed": False,
        "caution": "Snapshot provenance flags must be backed by independent VM hypervisor evidence.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()
    if args.before.resolve() == args.after.resolve():
        raise ValueError("before and after must be distinct evidence files")
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    result = compare(before, after)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["comparison_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
