"""F-13 offline HMAC challenge/response *contract*, DEV lab ONLY.

A shared test secret demonstrates integrity between two simulated peers.
No installed GUI, OS token, ACL, or real IPC is authenticated by this lab.
Even a valid HMAC MUST NOT imply permission for any RAG operation.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets

_SCHEMA = "RAG_DEL_F13_OFFLINE_GUI_CHALLENGE_V1"
_MAX_TTL_MS = 10_000
_HEX = frozenset("0123456789abcdef")
_FIELDS = frozenset((
    "schema", "nonce_hex", "snapshot_sha256", "gui_pid",
    "gui_birth_epoch_ms", "loaded_code_sha256", "issued_at_ms",
    "expires_at_ms",
))


def _digest(s: str) -> bool:
    return type(s) is str and len(s) == 64 and all(c in _HEX for c in s)


def _challenge_valid(challenge: dict) -> bool:
    if type(challenge) is not dict or set(challenge) != _FIELDS:
        return False
    nonce = challenge.get("nonce_hex")
    issued = challenge.get("issued_at_ms")
    expires = challenge.get("expires_at_ms")
    return (
        challenge["schema"] == _SCHEMA
        and _digest(nonce)
        and _digest(challenge["snapshot_sha256"])
        and _digest(challenge["loaded_code_sha256"])
        and type(challenge["gui_pid"]) is int and challenge["gui_pid"] > 0
        and type(challenge["gui_birth_epoch_ms"]) is int
        and challenge["gui_birth_epoch_ms"] > 0
        and type(issued) is int and issued > 0
        and type(expires) is int and issued < expires <= issued + _MAX_TTL_MS
    )


def make_offline_gui_challenge_dev(
    snapshot_sha256: str, gui_pid: int, gui_birth_epoch_ms: int,
    loaded_code_sha256: str, *, issued_at_ms: int, ttl_ms: int = 5000,
) -> dict:
    """Create a random lab challenge; does not send it to any process."""
    if not (
        _digest(snapshot_sha256) and _digest(loaded_code_sha256)
        and type(gui_pid) is int and gui_pid > 0
        and type(gui_birth_epoch_ms) is int and gui_birth_epoch_ms > 0
        and type(issued_at_ms) is int and issued_at_ms > 0
        and type(ttl_ms) is int and 0 < ttl_ms <= _MAX_TTL_MS
    ):
        raise ValueError("invalid offline challenge binding")
    challenge = {
        "schema": _SCHEMA,
        "nonce_hex": secrets.token_hex(32),
        "snapshot_sha256": snapshot_sha256,
        "gui_pid": gui_pid,
        "gui_birth_epoch_ms": gui_birth_epoch_ms,
        "loaded_code_sha256": loaded_code_sha256,
        "issued_at_ms": issued_at_ms,
        "expires_at_ms": issued_at_ms + ttl_ms,
    }
    assert _challenge_valid(challenge)
    return challenge


def _canonical(challenge: dict) -> bytes:
    return json.dumps(
        challenge, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("ascii")


def make_mock_gui_response_dev(challenge: dict, lab_secret: bytes) -> dict:
    """Simulated signer with caller-owned lab secret, NOT installed GUI proof."""
    if not _challenge_valid(challenge) or (
        type(lab_secret) is not bytes or len(lab_secret) < 32
    ):
        raise ValueError("invalid mock response input")
    return {
        "schema": "RAG_DEL_F13_OFFLINE_GUI_RESPONSE_V1",
        "challenge": dict(challenge),
        "mock_hmac_sha256": hmac.new(
            lab_secret, b"F13-MOCK-ONLY\x00" + _canonical(challenge),
            hashlib.sha256,
        ).hexdigest(),
    }


def review_mock_gui_response_dev(
    challenge: dict, response: dict, lab_secret: bytes, *,
    observed_at_ms: int, consumed_nonces: set[str],
) -> dict:
    """Verify test-only challenge integrity and replay, ALWAYS fail operationally.

    The consumed set belongs to the caller's lab session. No persistent
    production replay protection or installed-process trust is provided.
    """
    if (not _challenge_valid(challenge)
        or type(lab_secret) is not bytes or len(lab_secret) < 32
        or type(observed_at_ms) is not int or observed_at_ms <= 0
        or type(consumed_nonces) is not set
        or any(not _digest(v) for v in consumed_nonces)
    ):
        raise ValueError("invalid offline verification context")
    blockers = []
    response_ok = (
        type(response) is dict
        and set(response) == {"schema", "challenge", "mock_hmac_sha256"}
        and response.get("schema") == "RAG_DEL_F13_OFFLINE_GUI_RESPONSE_V1"
        and response.get("challenge") == challenge
        and _digest(response.get("mock_hmac_sha256"))
    )
    if not response_ok:
        blockers.append("MOCK_RESPONSE_MALFORMED_OR_WRONG_BINDING")
    else:
        actual = hmac.new(
            lab_secret, b"F13-MOCK-ONLY\x00" + _canonical(challenge),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(actual, response["mock_hmac_sha256"]):
            blockers.append("MOCK_HMAC_MISMATCH")
    if not challenge["issued_at_ms"] <= observed_at_ms <= challenge["expires_at_ms"]:
        blockers.append("MOCK_CHALLENGE_OUTSIDE_TIME_WINDOW")
    if challenge["nonce_hex"] in consumed_nonces:
        blockers.append("MOCK_CHALLENGE_REPLAY")
    lab_verified = not blockers
    if lab_verified:
        consumed_nonces.add(challenge["nonce_hex"])
    return {
        "state": "F13_MOCK_CONTRACT_VERIFIED_NO_INSTALLED_TRUST"
                 if lab_verified else "F13_MOCK_CONTRACT_REJECTED",
        "mock_contract_verified": lab_verified,
        "mock_nonce_consumed": lab_verified,
        "blockers": blockers + [
            "INSTALLED_GUI_TRUSTED_CHANNEL_UNVERIFIED",
            "INSTALLED_GUI_OS_PROCESS_IDENTITY_UNVERIFIED",
            "INSTALLED_GUI_LOADED_CODE_UNVERIFIED",
            "EFFECTIVE_WINDOWS_IPC_ACL_UNVERIFIED",
            "OPERATOR_QUEUE_JOURNAL_APPROVAL_REQUIRED",
        ],
        "dev_mock_only": True,
        "installed_gui_attested": False,
        "ready_for_operational_pilot": False,
        "activation_authorized": False,
        "operational_use_allowed": False,
        "read_only": True,
    }
