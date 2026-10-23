# P9-B reproducible Windows regression runner
Date: 2026-10-23
Status: regression tool certified; P9-B production update not authorized

New entrypoint: benchmarks/run_p9b_windows_regression.ps1
- Resolves the repository relative to the script location
- Uses the already installed external python.exe 3.13
- Borrows only the existing CodeBridge embedded Python psutil package path for this process and its child tests
- Adds repository/tests paths to PYTHONPATH without modifying packages or permanent environment variables
- Verifies psutil import, runs all test_rag_p9b_*.py with unittest discovery and restores original PYTHONPATH in finally
- Does not execute an installer, stop CodeBridge or alter public RAG data

Observed result from actual Windows PowerShell 5.1 invocation: 505 tests, OK, 48.656 seconds. External Python without psutil produced 10 import errors and supervisor failures; embedded isolated Python without inherited paths produced 10 subprocess failures. Neither is a validated regression environment.

Git and exact runtime remain authoritative; this is a test runner, not proof of production readiness or independently scheduled rollback control.