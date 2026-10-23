# P9-B Combined worker response hardening
Date: 2026-10-23
Status: isolated lab PASS; P9-B still OPEN

The combined recovery coordinator now rejects absent or invalid lab attestation and malformed file/shell/postverification worker outputs without advancing to later recovery steps. This prevents accidental attribute errors and makes the gate fail closed.

Files changed:
- installer/rag_p9b_combined_recovery_lab.py
- tests/test_rag_p9b_combined_recovery_lab.py

Verification: 7 direct tests PASS, 37 focused NSIS and journal recovery tests PASS, git diff audited, git diff --check PASS.

No live NSIS, public installation, registry keys or RAG index modified. This change does not constitute proof of a single crash-durable NSIS/HKCU/shortcut/file transaction.