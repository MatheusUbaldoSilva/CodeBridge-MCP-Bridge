"""Read-only identity gate for the detached combined rollback coordinator.

Confirms exact 4-artifact durable identity and ties it to the same target
installation and requested source commit. Does not authorize mutation.
"""
from __future__ import annotations

import json
from pathlib import Path
from installer.rag_p9b_transaction_identity import verify_identity, NAMES


def assess_detached_identity(*, manifest, manifest_sha256,
                             installed, expected_source_commit,
                             identity_probe=verify_identity):
    refused={"state":"DETACHED_COMBINED_IDENTITY_REFUSED",
             "verified":False,"read_only":True,
             "nsis_executed":False,"installed_modified":False,
             "cutover_authorized":False}
    try:
        proof=identity_probe(manifest,manifest_sha256)
        if (not isinstance(proof,dict)
                or proof.get("state")!="TRANSACTION_IDENTITY_VERIFIED"
                or proof.get("verified") is not True
                or proof.get("artifact_count")!=len(NAMES)):
            return {**refused,"reason":"FOUR_ARTIFACT_IDENTITY_INVALID"}
        body=json.loads(Path(manifest).read_text(encoding="utf-8"))
        if (Path(body["installed"]).resolve()!=Path(installed).resolve()
                or body.get("source_commit")!=expected_source_commit
                or proof.get("source_commit")!=expected_source_commit):
            return {**refused,"reason":"INSTALLED_OR_SOURCE_COMMIT_MISMATCH"}
        return {**refused,"state":"DETACHED_IDENTITY_OBSERVED_ONLY",
                "identity_verified":True,"artifacts_checked":len(NAMES),
                "requires_independent_stop_proof":True,
                "requires_production_rollback_postverify":True}
    except (OSError,ValueError,TypeError,KeyError):
        return {**refused,"reason":"IDENTITY_READ_FAILED"}
