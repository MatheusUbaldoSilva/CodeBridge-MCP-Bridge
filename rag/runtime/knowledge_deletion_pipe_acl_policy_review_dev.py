"""F14 conservative DEV policy review of caller-supplied G18 pipe ACE data.

This does NOT perform effective Windows AccessCheck, trust the producer,
validate identity of SID hashes, or inspect any live operating-system
handle. Even clean-looking ACEs NEVER grant RAG deletion authorization.
"""
from __future__ import annotations

import re

_BROAD = frozenset((
    "EVERYONE", "AUTHENTICATED_USERS", "ANONYMOUS_LOGON",
    "BUILTIN_USERS", "NETWORK", "INTERACTIVE", "SERVICE",
    "BUILTIN_GUESTS", "ALL_APPLICATION_PACKAGES",
    "ALL_RESTRICTED_APPLICATION_PACKAGES", "REMOTE_DESKTOP_USERS",
))
_SID_HEX = re.compile(r"[0-9a-f]{64}\Z")
_MASK_HEX = re.compile(r"[0-9a-f]{8}\Z")
_MAX_ACE = 64


def review_pipe_ace_inventory_policy_dev(record: dict) -> dict:
    """Review one *untrusted* pre-existing inventory record, no IO or ACL edits.

    Broad SIDs and malformed ACEs fail closed, but even private-looking
    DACLs do NOT establish effective access or process isolation.
    """
    if type(record) is not dict:
        raise ValueError("G18 record must be dict")
    if (record.get("activation_authorized") is not False
        or record.get("operational_use_allowed") is not False
        or record.get("read_only") is not True
        or record.get("private_acl_attested") is not False
        or record.get("effective_access_attested") is not False
        or record.get("child_handle_inheritance_attested") is not False):
        raise ValueError("operational or forged G18 authority rejected")
    count = record.get("ace_count")
    aces = record.get("aces")
    if type(aces) is not list or len(aces) > _MAX_ACE:
        raise ValueError("invalid bounded ACE list")
    observations = (
        record.get("state") == "WIN32_PIPE_ACE_INVENTORY_READ_ONLY"
        and record.get("dacl_observed") is True
        and type(count) is int and count == len(aces)
        and record.get("unsupported_ace_detected") is False
        and record.get("blockers") == []
    )
    blockers = []
    if not observations:
        blockers.append("WIN32_ACE_INVENTORY_NOT_VERIFIED")
    malformed = False
    broad = False
    unknown_allows = False
    allow_count = 0
    for ace in aces:
        if type(ace) is not dict or set(ace) != {
            "ace_type", "access_mask_hex", "principal_class", "sid_sha256"
        }:
            malformed = True
            continue
        kind, mask = ace["ace_type"], ace["access_mask_hex"]
        label, sid = ace["principal_class"], ace["sid_sha256"]
        if (kind not in ("ALLOW", "DENY")
            or type(mask) is not str or _MASK_HEX.fullmatch(mask) is None
            or type(label) is not str
            or label not in _BROAD | {"OTHER_PRINCIPAL"}
            or type(sid) is not str or _SID_HEX.fullmatch(sid) is None):
            malformed = True
            continue
        if kind == "ALLOW":
            allow_count += 1
            if label in _BROAD:
                # Intentionally conservative: any broad ALLOW is suspect,
                # regardless of mask. This is not an effective ACL calculation.
                broad = True
            else:
                # Hashed SID cannot be mapped to expected installed operator.
                unknown_allows = True
    if malformed:
        blockers.append("MALFORMED_OR_UNSUPPORTED_ACE")
    if broad or record.get("broad_allow_ace_detected") is True:
        blockers.append("BROAD_PRINCIPAL_ALLOW_ACE_OBSERVED")
    if unknown_allows:
        blockers.append("ALLOWED_SID_OWNER_BINDING_UNVERIFIED")
    if not allow_count:
        blockers.append("NO_ALLOW_ACE_OBSERVED")
    blockers.extend((
        "WINDOWS_EFFECTIVE_ACCESSCHECK_NOT_PERFORMED",
        "INSTALLED_PEER_TOKEN_AND_SESSION_UNVERIFIED",
        "PROCESS_HANDLE_INHERITANCE_UNVERIFIED",
        "OPERATOR_REVIEW_AND_APPROVAL_REQUIRED",
    ))
    return {
        "state": "F14_ACL_INVENTORY_REVIEW_BLOCKED",
        "schema": "RAG_DEL_F14_ACE_REVIEW_DEV_V1",
        "ace_metadata_consistent": bool(observations and not malformed),
        "broad_allow_ace_detected": bool(broad),
        "unknown_allow_sid_needs_owner_binding": bool(unknown_allows),
        "allow_ace_count": allow_count,
        "blockers": blockers,
        "source_only": True,
        "read_only": True,
        "effective_windows_access_attested": False,
        "installed_peer_token_attested": False,
        "ready_for_operational_pilot": False,
        "activation_authorized": False,
        "operational_use_allowed": False,
    }
