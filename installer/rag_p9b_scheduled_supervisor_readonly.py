"""Independent scheduled-task read-only supervisor gate.

The CLI only produces a durable attestation; never stops CodeBridge or runs
NSIS. A separate scheduled task may execute this Python process outside GUI.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

from installer.rag_p9b_detached_process_ancestry import inspect_detached_process_ancestry
from installer.rag_p9b_transaction_identity import verify_identity, digest
from installer.rag_p9b_same_machine_external_probe import inspect_external_runtime


def inspect_scheduled_supervisor(*,installed,stage,identity,identity_sha,
                                 expected_commit,interpreter,psutil_origin,
                                 runtime_probe=inspect_external_runtime,
                                 ancestry_probe=inspect_detached_process_ancestry,
                                 identity_probe=verify_identity):
    blocked={"state":"SCHEDULED_SUPERVISOR_REFUSED",
             "read_only":True,"authorized":False,
             "shutdown_signals_sent":False,"installer_executed":False,
             "production_modified":False}
    try:
        root=Path(installed).resolve(strict=True)
        stage=Path(stage).resolve(strict=True)
        identity=Path(identity).resolve(strict=True)
        dependency=stage/"external_supervisor_lib"
        if (not identity.is_relative_to(stage)
                or not dependency.is_dir() or dependency.is_symlink()
                or not isinstance(expected_commit,str)
                or len(expected_commit)!=40):
            return {**blocked,"reason":"STAGING_SCOPE_INVALID"}
        runtime=runtime_probe(installed=root,interpreter=interpreter,
            psutil_origin=psutil_origin,staged_lib=dependency)
        if (not isinstance(runtime,dict)
                or runtime.get("state")!="EXTERNAL_RUNTIME_PATHS_VERIFIED"
                or runtime.get("verified") is not True):
            return {**blocked,"reason":"EXTERNAL_RUNTIME_REQUIRED"}
        ancestry=ancestry_probe(installed=root)
        if (not isinstance(ancestry,dict)
                or ancestry.get("state")!="EXTERNAL_PROCESS_ANCESTRY_VERIFIED"
                or ancestry.get("verified") is not True):
            return {**blocked,"reason":"EXTERNAL_ANCESTRY_REQUIRED"}
        if (not isinstance(identity_sha,str)
                or digest(identity)!=identity_sha.lower()):
            return {**blocked,"reason":"IDENTITY_DIGEST_MISMATCH"}
        proof=identity_probe(identity,identity_sha.lower())
        if (not isinstance(proof,dict)
                or proof.get("verified") is not True
                or proof.get("source_commit")!=expected_commit):
            return {**blocked,"reason":"TRANSACTION_IDENTITY_INVALID"}
        return {**blocked,"state":"SCHEDULED_SUPERVISOR_READONLY_ATTESTED",
                "external_runtime_verified":True,
                "ancestry_verified":True,"identity_verified":True,
                "reason":"MUTATING_SUPERVISOR_NOT_CERTIFIED"}
    except Exception:
        return {**blocked,"reason":"SCHEDULED_ATTESTATION_FAILED"}


def main(argv=None):
    parser=argparse.ArgumentParser()
    for name in ("installed","stage","identity","identity-sha",
                 "expected-commit","result"):
        parser.add_argument("--"+name,required=True)
    args=parser.parse_args(argv)
    stage=Path(args.stage)
    dependency=stage/"external_supervisor_lib"
    if dependency.is_dir() and not dependency.is_symlink():
        sys.path.insert(0,str(dependency))
    try:
        import psutil
        origin=psutil.__file__
    except Exception:
        origin=""
    report=inspect_scheduled_supervisor(installed=args.installed,
        stage=args.stage,identity=args.identity,
        identity_sha=args.identity_sha,expected_commit=args.expected_commit,
        interpreter=sys.executable,psutil_origin=origin)
    output=Path(args.result).absolute()
    if output.is_symlink() or output.exists() or not output.parent.is_dir():
        return 2
    with output.open("x",encoding="utf-8") as stream:
        json.dump(report,stream,sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(report,sort_keys=True))
    return 2


if __name__=="__main__":
    raise SystemExit(main())
