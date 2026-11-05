"""Read-only and fail-closed admission precheck for a future deletion channel.

A successful precheck is not operational permission: caller-provided
attestation fields are not trusted without independent server verification.
No IPC listener, data mutation, or authorization is provided.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import re
import time

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_PROJECT = re.compile(r"[a-z][a-z0-9_-]{1,63}\Z")

def selection_sha256(project_id: str, paths: list[str], generation: str) -> str:
    if not isinstance(project_id,str) or not _PROJECT.fullmatch(project_id) or project_id == "codebridge":
        raise ValueError("invalid private project")
    if not isinstance(generation,str) or not generation or len(generation)>180 or any(ord(x)<33 for x in generation):
        raise ValueError("invalid generation")
    if (not isinstance(paths,list) or not 0<len(paths)<=256
        or any(not isinstance(p,str) or not p or len(p)>1024
               or any(ord(c)<32 for c in p)
               or "\\" in p or p.startswith("/")
               or any(part in ("", ".", "..") for part in p.split("/"))
               for p in paths)
        or paths != sorted(set(paths))):
        raise ValueError("invalid selected paths")
    payload=json.dumps(dict(project_id=project_id,generation=generation,selected_paths=paths),
                       ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def review_operational_deletion_admission(request:dict,*,gui_witness:dict,
                                          operational_inventory:dict,
                                          target_conflicts:dict|None=None,
                                          now_epoch:int|None=None)->dict:
    result=dict(state="RAG_DEL_COMMAND_ADMISSION_BLOCKED",read_only=True,
                activation_authorized=False,deletion_enabled=False,
                operational_use_allowed=False,request_selection_sha256=None,
                blockers=[])
    blockers=result["blockers"]
    if type(request) is not dict or type(gui_witness) is not dict or type(operational_inventory) is not dict:
        blockers.append("INVALID_RECEIPTS")
        return result
    try:
        project=request.get("project_id")
        generation=request.get("generation")
        digest=selection_sha256(project,request.get("selected_paths"),generation)
        result["request_selection_sha256"]=digest
    except (ValueError,TypeError,UnicodeError):
        blockers.append("INVALID_BOUND_SELECTION")
        return result
    if type(request.get("selection_sha256")) is not str or not hmac.compare_digest(request["selection_sha256"],digest):
        blockers.append("SELECTION_DIGEST_MISMATCH")
    if any(type(request.get(name)) is not str or not _HEX64.fullmatch(request[name])
           for name in ("review_sha256","catalog_sha256","public_pointer_sha256")):
        blockers.append("IMMUTABLE_REVIEW_PINS_MISSING")
    now=int(time.time()) if now_epoch is None else now_epoch
    created=request.get("created_epoch")
    if (type(now) is not int or type(created) is not int
            or created>now or now-created>120):
        blockers.append("REVIEW_EXPIRED")
    if (gui_witness.get("state")!="GUI_LOADED_CODE_KERNEL_PINNED_READONLY"
        or gui_witness.get("installed_gui_loaded_code_observed") is not True
        or gui_witness.get("expected_loaded_code_matches") is not True
        or gui_witness.get("peer_accesscheck_observed") is not True
        or gui_witness.get("challenge_bound") is not True
        or type(gui_witness.get("expected_pid")) is not int
        or gui_witness.get("observed_server_pid")!=gui_witness.get("expected_pid")):
        blockers.append("GUI_WITNESS_MISSING")
    # The client cannot attest itself. No operational deletion channel exists yet.
    # This admission helper is only a read-only protocol precursor.
    blockers.append("OPERATIONAL_IPC_NOT_ATTESTED")
    if target_conflicts is None:
        if (operational_inventory.get("read_only") is not True
            or type(operational_inventory.get("queue_pending_count")) is not int
            or operational_inventory.get("queue_pending_count")!=0
            or type(operational_inventory.get("canary_count")) is not int
            or operational_inventory.get("canary_count")!=0
            or operational_inventory.get("canary_catalog_consistent") is not True
            or operational_inventory.get("public_generation")!=generation
            or operational_inventory.get("blockers")!=[]):
            blockers.append("QUEUE_OR_CANARY_NOT_QUIET")
    elif (type(target_conflicts) is not dict
          or target_conflicts.get("state")!="TARGET_CONFLICTS_CLEAR_FOR_READONLY_PLANNING"
          or target_conflicts.get("read_only") is not True
          or target_conflicts.get("project_id")!=project
          or target_conflicts.get("target_isolation_proven") is not True
          or target_conflicts.get("catalog_cas_required") is not True
          or target_conflicts.get("target_queue_jobs")!=0
          or target_conflicts.get("target_active_canaries")!=0
          or target_conflicts.get("catalog_sha256")!=request.get("catalog_sha256")
          or target_conflicts.get("public_pointer_sha256")!=request.get("public_pointer_sha256")
          or target_conflicts.get("blockers")!=[]):
        blockers.append("TARGET_PROJECT_CONFLICT_OR_CAS_PIN_MISSING")
    if (type(target_conflicts) is dict
            and type(target_conflicts.get("unrelated_active_canaries")) is int
            and target_conflicts.get("unrelated_active_canaries") > 0):
        # Even an unrelated AUTO canary pins the SHA of the entire shared
        # catalog. A concurrent catalog update breaks its rollback journal.
        blockers.append("SHARED_CATALOG_CANARY_PIN_BLOCKS_ANY_WRITE")
    if request.get("operator_confirmation")!="RAG_DEL_REVIEW:"+project+":"+digest:
        blockers.append("PROJECT_AND_SELECTION_CONFIRMATION_MISSING")
    if not blockers:
        result["state"]="RAG_DEL_ADMISSION_PRECHECK_CLEAN_NOT_AUTHORIZED"
    return result
