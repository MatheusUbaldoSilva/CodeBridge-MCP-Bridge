"""F-12: join one caller-supplied DEV process snapshot with offscreen GUI evidence.

The snapshot SHA256 is a reproducibility receipt, NOT an authenticity proof.
No installed GUI channel is contacted. Never allow deletion or pilot here.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from rag.runtime.knowledge_deletion_gui_process_observer_dev import (
    review_gui_process_topology_dev,
)
from rag.runtime.knowledge_deletion_gui_creation_order_dev import (
    review_gui_creation_order_dev,
)
from rag.runtime.knowledge_deletion_gui_boundary_review_dev import (
    review_gui_install_attestation_gap_dev,
)

_MAX_PROCESSES = 64
_MAX_COMMAND = 32768


def _snapshot_receipt(processes: list[dict]) -> str:
    """Canonical caller-data receipt; intentionally never a trusted signature."""
    if type(processes) is not list or not 1 <= len(processes) <= _MAX_PROCESSES:
        raise ValueError("invalid bounded DEV process snapshot")
    observed = []
    seen = set()
    for item in processes:
        if type(item) is not dict:
            raise ValueError("invalid process record")
        pid = item.get("ProcessId")
        parent = item.get("ParentProcessId")
        birth = item.get("CreationEpochMs")
        command = item.get("CommandLine")
        if (type(pid) is not int or pid <= 0 or pid in seen
                or type(parent) is not int or parent < 0
                or type(birth) is not int or birth <= 0
                or type(command) is not str or not 0 < len(command) <= _MAX_COMMAND
                or "\x00" in command):
            raise ValueError("invalid snapshot identity fields")
        seen.add(pid)
        # Copy only the four required observation fields, never extra caller
        # authority claims or mutation/approval metadata.
        observed.append(dict(
            ProcessId=pid, ParentProcessId=parent,
            CreationEpochMs=birth, CommandLine=command,
        ))
    payload = json.dumps(
        dict(schema="RAG_DEL_F12_DEV_PROCESS_SNAPSHOT_V1",
             records=sorted(observed, key=lambda x: x["ProcessId"])),
        ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def review_gui_evidence_package_dev(
    processes: list[dict], dev_root: Path, offscreen_lab: dict, *,
    expected_snapshot_sha256: str | None = None,
) -> dict:
    """Fail closed on inconsistent metadata; never attest installed processes.

    An optional previous receipt detects changed caller data. Matching does
    NOT prove freshness, process identity, or OS provenance.
    """
    if not isinstance(dev_root, Path) or not dev_root.is_absolute():
        raise ValueError("invalid DEV root")
    if type(offscreen_lab) is not dict:
        raise ValueError("missing offscreen diagnostic evidence")
    if expected_snapshot_sha256 is not None and (
            type(expected_snapshot_sha256) is not str
            or len(expected_snapshot_sha256) != 64
            or any(c not in "0123456789abcdef" for c in expected_snapshot_sha256)):
        raise ValueError("invalid prior snapshot receipt")
    current = _snapshot_receipt(processes)
    # Both observers reconstruct their results from exactly this snapshot;
    # caller cannot supply independently asserted topology or birth order.
    topology = review_gui_process_topology_dev(processes, dev_root)
    chronology = review_gui_creation_order_dev(processes, dev_root)
    boundary = review_gui_install_attestation_gap_dev(topology, offscreen_lab)
    same_snapshot = (
        expected_snapshot_sha256 is None
        or expected_snapshot_sha256 == current
    )
    top_ok = topology["expected_dev_process_tree_observed"] is True
    birth_ok = chronology["process_creation_order_observed"] is True
    lab_ok = boundary["checks"]["offscreen_lab_gui_code_observed"] is True
    blockers = []
    if not same_snapshot:
        blockers.append("DEV_PROCESS_SNAPSHOT_CHANGED")
    if not top_ok:
        blockers.append("DEV_PROCESS_TOPOLOGY_UNVERIFIED")
    if not birth_ok:
        blockers.append("DEV_PROCESS_BIRTH_ORDER_UNVERIFIED")
    if not lab_ok:
        blockers.append("OFFSCREEN_LAB_GUI_CODE_UNVERIFIED")
    # Operational blockers remain unconditional, even if all lab/OS claims
    # appear positive, and must not be removed by a forged metadata record.
    blockers.extend((
        "INSTALLED_GUI_TRUSTED_CHANNEL_UNVERIFIED",
        "INSTALLED_GUI_PID_AND_BIRTH_UNVERIFIED",
        "INSTALLED_GUI_LOADED_CODE_UNVERIFIED",
        "EFFECTIVE_IPC_TOKEN_ACL_UNVERIFIED",
        "OPERATOR_QUEUE_JOURNAL_APPROVAL_REQUIRED",
    ))
    return dict(
        state="F12_DEV_SNAPSHOT_COHERENT_INSTALLED_UNVERIFIED"
              if same_snapshot and top_ok and birth_ok and lab_ok
              else "F12_DEV_SNAPSHOT_UNVERIFIED",
        schema="RAG_DEL_F12_DEV_EVIDENCE_PACKAGE_V1",
        process_snapshot_sha256=current,
        process_snapshot_source="CALLER_SUPPLIED_DEV_METADATA_UNTRUSTED",
        snapshot_receipt_matches=bool(same_snapshot),
        checks=dict(
            process_argv_topology_observed=bool(top_ok),
            process_creation_order_observed=bool(birth_ok),
            offscreen_gui_code_observed=bool(lab_ok),
            installed_gui_attested=False,
            installed_gui_challenge_response_attested=False,
            effective_ipc_acl_token_isolation_verified=False,
        ),
        blockers=blockers,
        source_only=True,
        read_only=True,
        installed_gui_attested=False,
        installed_gui_runtime_proven=False,
        ready_for_operational_pilot=False,
        activation_authorized=False,
        operational_use_allowed=False,
    )
