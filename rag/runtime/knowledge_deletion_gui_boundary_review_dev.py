"""F-9: preserve trust boundary between GUI topology, offscreen lab and install.

Combining two independent observations is not a trusted channel. In particular
the GUI process tree and offscreen QWidget may be different processes.
"""
from __future__ import annotations

def review_gui_install_attestation_gap_dev(topology:dict,lab:dict)->dict:
    if type(topology) is not dict or type(lab) is not dict:
        raise ValueError("two read-only diagnostic records required")
    if (topology.get("read_only") is not True
        or lab.get("read_only") is not True
        or topology.get("activation_authorized") is not False
        or lab.get("activation_authorized") is not False):
        raise ValueError("untrusted or operational evidence rejected")
    topology_ok=(
        topology.get("state")=="GUI_PROCESS_TOPOLOGY_OBSERVED_ONLY"
        and topology.get("expected_dev_process_tree_observed") is True
        and topology.get("argv_script_paths_exactly_matched") is True
        and topology.get("loaded_python_module_attested") is False
        and topology.get("gui_runtime_attested") is False
    )
    checks=lab.get("checks")
    lab_ok=(
        lab.get("state")=="DEV_GUI_INPROCESS_READER_OBSERVED"
        and lab.get("lab_inprocess_observed") is True
        and isinstance(checks,dict)
        and checks.get("gui_route_loaded_bytecode_matches_dev_file") is True
        and checks.get("reader_loaded_bytecode_matches_dev_file") is True
        and checks.get("on_gui_owner_thread") is True
        and lab.get("installed_gui_trusted_channel_attested") is False
        and lab.get("gui_runtime_attested_for_operational_deletion") is False
        and isinstance(lab.get("code_receipt_sha256"),str)
        and len(lab["code_receipt_sha256"])==64
    )
    checks={
        "real_gui_process_tree_observed":bool(topology_ok),
        "offscreen_lab_gui_code_observed":bool(lab_ok),
        "installed_gui_ipc_challenge_response_attested":False,
        "installed_gui_pid_and_birth_bound":False,
        "installed_gui_loaded_code_verified_by_trusted_channel":False,
    }
    blockers=[name for name,ok in checks.items() if not ok]
    return dict(
        state="INSTALLED_GUI_RUNTIME_ATTESTATION_UNRESOLVED",
        checks=checks,blockers=blockers,
        lab_and_process_claims_joined_as_installed_proof=False,
        installed_gui_attested=False,
        activation_authorized=False,operational_use_allowed=False,
        ready_for_operational_pilot=False,read_only=True,
    )
