"""Lab-only adapter: durable attempt reservation -> existing combined recovery.

No scheduler registration, no production deployment, no installer execution.
The existing detached combined lab owns all restore operations and scope guards.
"""
from __future__ import annotations
import json
import tempfile
from pathlib import Path
from installer.rag_p9b_frozen_disposable_bundle import _contained
from installer.rag_p9b_recovery_retry_ledger import (
    reserve_disposable_retry, mark_disposable_retry_terminal,
)


def run_lab_retry(*, config, retry_ledger, transaction_sha256, worker=None,
                  temp_root=None):
    blocked = dict(state="P9B_SCHEDULED_LAB_RETRY_REFUSED", verified=False,
                   production_modified=False, cutover_authorized=False)
    root = Path(temp_root or tempfile.gettempdir()).resolve(strict=True)
    actual_temp = Path(tempfile.gettempdir()).resolve(strict=True)
    cfg = Path(config).absolute()
    ledger = Path(retry_ledger).absolute()
    if (root != actual_temp and actual_temp not in root.parents
            or not _contained(cfg, root) or not cfg.is_file() or cfg.is_symlink()
            or not _contained(ledger.parent, root) or ledger.is_symlink()
            or ledger.parent != cfg.parent):
        return {**blocked, "reason": "LAB_CONFIG_OR_LEDGER_SCOPE_INVALID"}
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        raw_lab = Path(data["lab"]).absolute()
        if not _contained(raw_lab, root):
            return {**blocked, "reason": "DISPOSABLE_ROOT_REQUIRED"}
        lab = raw_lab.resolve(strict=True)
        if lab.name != "disposable" or not _contained(lab, root):
            return {**blocked, "reason": "DISPOSABLE_ROOT_REQUIRED"}
        required = ("journal", "installed", "appdata", "desktop",
                    "snapshot", "shell_snapshot", "preimage", "token")
        if any(not isinstance(data.get(key), str) or not data[key] for key in required):
            return {**blocked, "reason": "RECOVERY_CONFIGURATION_INCOMPLETE"}
        if (Path(data["journal"]).absolute().parent != cfg.parent
                or Path(data["journal"]).is_symlink()):
            return {**blocked, "reason": "JOURNAL_LOCATION_INVALID"}
        for name in ("appdata", "desktop"):
            if not _contained(data[name], lab):
                return {**blocked, "reason": "SHELL_OUTSIDE_SCRATCH"}
        for name in ("snapshot", "shell_snapshot", "preimage"):
            if not _contained(data[name], root) or not Path(data[name]).is_file():
                return {**blocked, "reason": "BACKUP_OUTSIDE_SCRATCH"}
        installed = Path(data["installed"]).absolute()
        if installed == lab or installed in lab.parents or lab in installed.parents:
            return {**blocked, "reason": "LIVE_INSTALL_PATH_REJECTED"}
        if worker is None:
            from installer.rag_p9b_detached_combined_recovery_lab import execute
            worker = execute
        if not callable(worker):
            return {**blocked, "reason": "WORKER_INVALID"}
        attempt = reserve_disposable_retry(ledger, transaction_sha256=transaction_sha256,
                                           temp_root=root)
        if not attempt.get("reserved"):
            return {**blocked, "reason": attempt.get("reason", "RESERVATION_REFUSED"),
                    "retry_state": attempt.get("state"),
                    "attempts": attempt.get("attempts")}
        outcome = worker(str(cfg))
        if not isinstance(outcome, dict) or outcome.get("verified") is not True:
            return {**blocked, "state": "P9B_RETRY_RECOVERY_REVIEW_REQUIRED",
                    "reason": "COMBINED_RECOVERY_UNVERIFIED",
                    "attempt": attempt["attempt"]}
        if outcome.get("production_modified") is not False:
            return {**blocked, "reason": "WORKER_PRODUCTION_SCOPE_UNVERIFIED"}
        terminal = mark_disposable_retry_terminal(
            ledger, transaction_sha256=transaction_sha256,
            temp_root=root, postverified=True)
        if terminal.get("state") != "P9B_TERMINAL_PERSISTED":
            return {**blocked, "reason": "TERMINAL_NOT_DURABLE",
                    "attempt": attempt["attempt"]}
        return {**blocked, "state": "P9B_LAB_COMBINED_TERMINAL_PERSISTED",
                "verified": True, "attempt": attempt["attempt"],
                "requires_source_authentication": True,
                "requires_real_nsis_transaction_proof": True}
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        return {**blocked, "reason": "LAB_RETRY_EXECUTION_FAILED"}