# P9-B - Scheduled isolated worker SHA256 source gate
Date: 2026-10-23
State: ISOLATED LAB PASSED; P9-B OPEN

The Scheduled Task wrapper now snapshots SHA256 for six relevant repository files into its disposable request before launch. The separate worker recomputes all six before import; absent, changed, redirected or missing source fails closed with INDEPENDENT_LAB_REFUSED. This prevents unobserved changes between task registration and worker startup in a cooperative laboratory. Because the manifest and source are both in user-writable locations this is a consistency gate, not a cryptographic signature nor a hostile-tampering security guarantee.

Files:
- installer/p9b_scheduled_combined_lab.ps1: request SHA256 map and independent Python pre-import verification
- tests/test_rag_p9b_scheduled_combined_lab.py: parser and content assertions

Evidence: 2 dedicated tests PASS, actual Windows Scheduled Task returned SCHEDULED_COMBINED_LAB_VERIFIED, tests=7, ancestry_verified=true, isolated_nsis_test_executed=true, production_nsis_executed=false, production_modified=false. No modification to installed CodeBridge, real application keys or RAG index.

Pending: immutable signed source staging with independent trust anchor, crash-persistent self-restarting recovery worker, and maintenance-authorized production cutover.