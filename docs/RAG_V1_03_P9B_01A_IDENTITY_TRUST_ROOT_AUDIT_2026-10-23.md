# P9-B.01-A - Identity contract audit
Baseline: 6466af351ca7744ee70ab21cfcce67a12fd3884e (HEAD/upstream)
Status: inventory complete; 01-B/C/D OPEN, P9-B OPEN

| Layer | Current proof | Gap | Required test |
| --- | --- | --- | --- |
| Four-artifact identity | write_identity/verify_identity bind installer, file_snapshot, shell_snapshot, crash_preimage and source commit by SHA256 | Caller controls expected manifest SHA and commit; no independent authentication | Reject jointly substituted manifest plus digest |
| Combined identity gate | assess_detached_identity checks installed and source commit in read-only mode | Externally supplied trust root and TOCTOU between check/use | Frozen immutable package and identity check at consumption |
| Windows Scheduled Task | Six source hashes in TEMP and eight isolated lab tests | Same-user-writable request and source, imports outside six-file coverage | Frozen transitive source with mutation and reparse refusal |
| Journal | fsync, sequence, OS advisory sidecar locking | Not signed; cooperative same-host lock, user can rewrite | Independent trust anchor and tamper refusal |
| NSIS artifact | Installer SHA in existing V1 identity | No authoritative signed digest for worker launch | Match verified package and executed NSIS digest |
| Scope | Installed root and three rollback artifacts bound | appdata/desktop/HKCU absent from V1 identity | Scoped manifest with canonical TEMP roots |
| Production | Official authorized=False, read-only gates | Lab PASS does not authorize cutover | Explicit operator gate then CBMCP/1/RAG reconnect |

Trusted public key, independent signer, protected ACL or separate trust authority was NOT evidenced in the audited modules. Report TRUST_ROOT_UNVERIFIED, not a signed update. SHA256 request only proves consistency.

Next: 01-B build disposable frozen lab bundle using existing contracts; 01-C requires independent authentication; 01-D negative tests and audit. Never mutate installed CodeBridge.
Preserve historical dirty paths:
- benchmarks/rag017_code_only_extended_smoke.json
- docs/RAG_017_J_VM_ROLLBACK_RUNBOOK_2026-10-10.md
- rag/runtime/incremental_installed_queue_init.py