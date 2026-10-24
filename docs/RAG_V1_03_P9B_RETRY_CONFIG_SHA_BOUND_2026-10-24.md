# P9-B.02-C — Bind disposable bounded retry transaction to config content
Date: 2026-10-24
Status: 600 P9B tests PASS. P9-B remains OPEN.

The disposable scheduled-combined retry adapter now hashes raw config bytes (SHA-256) before JSON parsing and before reserving an attempt. Caller-supplied transaction_sha256 must equal that exact digest or fail closed TRANSACTION_CONFIG_SHA_MISMATCH without touching retry ledger. Existing real scoped HKCU/236 existing/22 newly removed/5 shortcuts/two registry recovery fixtures compute SHA-256 over their own config and continue passing. Unit tests now bind hashes to fixture bytes; a mutation after binding is refused.

This only establishes consistency between caller-provided digest and file bytes at initial read. It is NOT a publisher signature, independently protected trust anchor, frozen mutable configuration during worker run, or official NSIS update authorization. Future P9-B.01-C root authenticity, P9-B.02 unified installer+rollback transaction and P9-B.03 automatic scheduled full recovery remain pending.