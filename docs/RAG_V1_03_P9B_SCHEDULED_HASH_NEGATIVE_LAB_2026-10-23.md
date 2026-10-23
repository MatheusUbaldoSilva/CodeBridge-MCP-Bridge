# P9-B - Scheduled worker source mismatch negative test
Date: 2026-10-23
Status: isolated negative and positive gates PASS; P9-B OPEN

The Windows Scheduled Task test harness accepts a lab-only -InjectHashMismatchForLab flag which changes the SHA256 in its disposable request, not repository files. This intentionally mismatches one of the six source hashes.

Actual test with the temporary Task Scheduler worker:
- The worker returned INDEPENDENT_LAB_REFUSED, reason SOURCE_IDENTITY_MISMATCH before importing the recovery executor
- The outer PowerShell command correctly failed with LAB_FAILED_OR_UNVERIFIED and the mismatch reason
- No temporary scheduled task remained afterward
- A subsequent positive run without injection passed SCHEDULED_COMBINED_LAB_VERIFIED, tests=7, production_modified=false

The request remains user-writable so this only proves fail-closed consistency under mismatched hashes and does not authenticate an attacker-controlled manifest. No production installer, public HKCU keys, MCP lifecycle or RAG index were modified.