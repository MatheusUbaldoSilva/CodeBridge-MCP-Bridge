# P9-B.01-B - Frozen disposable bundle
State: lab prototype tested. NOT source-authenticated. P9-B.01-C still blocked on independent trust anchor.

New: installer/rag_p9b_frozen_disposable_bundle.py
New: tests/test_rag_p9b_frozen_disposable_bundle.py

The disposable TEMP-only preflight copies the existing four V1 artifacts to independent bytes, fsyncs copies, checks original before/after copy, writes a canonical deterministic manifest with transaction_id, full source commit, installed/appdata/desktop and isolated HKCU prefix. Read-only verification recomputes the manifest and four artifact hashes. Caller cannot broaden custom TEMP root to filesystem root; duplicate JSON keys and scope outside TEMP refuse. This is consistency, NOT authenticity and not a signed trust root.

Validation: 12 focused tests PASS, 526 full P9B tests PASS (50.566 seconds), no public NSIS run and no installed CodeBridge changed. Existing rollback code and official authorization gates were not modified.

Follow-up 01-C: authoritative independent trust root; no cutover without it. 01-D: adversarial TOCTOU/reparse and changed-commit proofs. P9-B remains OPEN.