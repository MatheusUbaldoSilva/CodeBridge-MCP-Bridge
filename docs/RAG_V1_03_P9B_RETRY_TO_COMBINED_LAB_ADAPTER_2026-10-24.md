# P9-B.02/03 — Bounded retry adapter for existing combined disposable rollback
Date: 2026-10-24
Status: PREPARATORY; NOT genuine isolated NSIS crash-durable atomic transaction.
P9-B OPEN.

Reused existing installer/rag_p9b_detached_combined_recovery_lab.py and existing OS-locked retry ledger. New installer/rag_p9b_scheduled_combined_retry_adapter.py validates TEMP-only config, lexical non-symlink lab path named disposable, backups and appdata/desktop scratch scope, same-folder journal and ledger. Then reserves a bounded attempt before invoking existing detached recovery; only its verified=True, production_modified=False response permits fsync terminal mark. No scheduler registration or production executor introduced.

Tests: 12 focused adapter tests PASS: terminal prevents duplicate worker, retry budget, verified-only terminal, wrong transaction SHA, malformed config, outside path, backup escape, symlink lab, shell escape, worker exception. Full P9B suite: 589 PASS in 52.366s. Tests use injected stub workers and DO NOT prove real detached recovery in this adapter. The existing separate scheduled actual isolated NSIS lab suite remains a distinct proof.

Gap: worker invocation consumes mutable JSON and no independently authenticated root; passing an injected worker can only be trusted for unit tests, not for production. Future milestone must run existing detached real lab through this adapter with frozen source identity, crash after files/shell, and source-authenticated journal spanning installer/files/HKCU/shortcuts. Do not enable any official installer.