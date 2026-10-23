"""Fail-closed crash triage for a detached P9-B Windows supervisor.

Read-only: does not re-run recovery workers, stop/restart CodeBridge or run NSIS.
"""
from __future__ import annotations

import json
from pathlib import Path

from installer.rag_p9b_detached_combined_identity_gate import assess_detached_identity
from installer.rag_p9b_rollback_journal import RollbackJournal, read_journal
from installer.rag_p9b_poststop_verification import check_poststop


def triage_crash(*, installed, identity_manifest, identity_sha256,
                 source_commit, journal_path,
                 identity_probe=assess_detached_identity,
                 journal_probe=read_journal,
                 stop_probe=check_poststop,
                 resume_probe=RollbackJournal.resume):
    denied={"state":"DETACHED_CRASH_TRIAGE_REFUSED",
            "authorized":False,"read_only":True,
            "recovery_executed":False,"installer_executed":False,
            "installed_modified":False}
    try:
        proof=identity_probe(
            manifest=identity_manifest,manifest_sha256=identity_sha256,
            installed=installed,expected_source_commit=source_commit)
        if (not isinstance(proof,dict)
                or proof.get("state")!="DETACHED_IDENTITY_OBSERVED_ONLY"
                or proof.get("identity_verified") is not True
                or proof.get("artifacts_checked")!=4):
            return {**denied,"reason":"IDENTITY_NOT_BOUND"}
        journal=journal_probe(journal_path)
        if (not isinstance(journal,dict)
                or journal.get("state")!="JOURNAL_OBSERVED_ONLY"
                or journal.get("count",0)<1):
            return {**denied,"reason":"JOURNAL_NOT_VERIFIED"}
        # The resume validator requires the original first-event identity,
        # and rejects journals that claim terminal success or have bad history.
        resume_probe(journal_path,expected_transaction_sha256=identity_sha256)
        stopped=stop_probe(Path(installed))
        if (not isinstance(stopped,dict)
                or stopped.get("state")!="POSTSTOP_OBSERVED_ONLY"
                or stopped.get("observed_stopped") is not True):
            return {**denied,"state":"DETACHED_CRASH_ACTIVE_REVIEW_REQUIRED",
                    "reason":"PROCESSES_STILL_ACTIVE_OR_UNVERIFIED"}
        return {**denied,"state":"DETACHED_CRASH_RECOVERY_REVIEW_REQUIRED",
                "journal_last_state":journal.get("last_state"),
                "journal_events":journal["count"],
                "reason":"RECOVERY_WORKER_NOT_AUTOMATICALLY_AUTHORIZED"}
    except (OSError,ValueError,TypeError,KeyError):
        return {**denied,"reason":"CRASH_TRIAGE_VALIDATION_FAILED"}


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--installed",required=True)
    parser.add_argument("--identity",required=True)
    parser.add_argument("--identity-sha",required=True)
    parser.add_argument("--source-commit",required=True)
    parser.add_argument("--journal",required=True)
    args=parser.parse_args(argv)
    result=triage_crash(installed=args.installed,
        identity_manifest=args.identity,
        identity_sha256=args.identity_sha,source_commit=args.source_commit,
        journal_path=args.journal)
    print(json.dumps(result,sort_keys=True))
    return 2


if __name__=="__main__":
    raise SystemExit(main())
