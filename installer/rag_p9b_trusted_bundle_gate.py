"""Fail-closed Ed25519 identity proof for P9-B frozen bundle.

Verifying signature math is not sufficient to trust a publisher. A protected
out-of-band trust root must be attested by a distinct authorized component.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from installer.rag_p9b_frozen_disposable_bundle import verify_disposable_bundle


def verify_signed_frozen_bundle(*, manifest, signature, public_key,
                                expected_manifest_sha256, trusted_root_proof=None,
                                temp_root=None):
    refused = {"state": "TRUST_ROOT_UNVERIFIED", "verified": False,
               "trusted_origin": False, "production_modified": False,
               "cutover_authorized": False}
    consistency = verify_disposable_bundle(
        manifest, expected_manifest_sha256, temp_root=temp_root)
    if consistency.get("verified") is not True:
        return {**refused, "reason": "BUNDLE_INCONSISTENT",
                "bundle_reason": consistency.get("reason")}
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        manifest_bytes = Path(manifest).read_bytes()
        signature_bytes = Path(signature).read_bytes()
        key_bytes = bytes(public_key)
        if len(signature_bytes) != 64 or len(key_bytes) != 32:
            return {**refused, "reason": "SIGNATURE_FORMAT_INVALID"}
        Ed25519PublicKey.from_public_bytes(key_bytes).verify(
            signature_bytes, manifest_bytes)
    except (OSError, ValueError, TypeError, ImportError, Exception) as error:
        # A signature never grants permission to run NSIS on its own.
        return {**refused, "reason": "SIGNATURE_NOT_VERIFIED",
                "exception_type": type(error).__name__}
    key_fingerprint = hashlib.sha256(key_bytes).hexdigest()
    # Never trust caller-supplied attestations: a dict can be forged with the
    # signature. Authentication requires a separately implemented, protected
    # verifier. None is installed for this P9-B lab.
    return {**refused, "reason": "INDEPENDENT_TRUST_ROOT_MISSING",
            "signature_valid": True, "public_key_sha256": key_fingerprint}