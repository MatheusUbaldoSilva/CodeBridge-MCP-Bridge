# P9-B incremental test diagnosis 2026-10-23

P9-B OPEN, NSIS production cutover NOT performed.

58 files audited individually with Python313 external and 8-second diagnostic timeout:
- 52 PASS
- 5 TIMEOUT >8 seconds (INCONCLUSIVE not product failure)
- 1 import error (external Python lacks mcp package)

Slow files: test_incremental_installed_worker_e2e.py;
test_incremental_offline_worker.py; test_incremental_worker_build_heartbeat.py;
test_incremental_worker_real_process_e2e.py; test_incremental_worker_receipt.py.

test_incremental_queue_bootstrap_mcp_tool.py PASSED 4 tests with installed
embedded Python and repository root explicitly first in sys.path.
The embedded environment includes mcp 2.2.0. Without explicit sys.path,
embedded Python loads installed rag.runtime instead of repository source.

Follow-up: run the five slow test files individually with appropriate
timeouts and distinguish runtime cost from deadlocks. Full aggregate suite
is NOT certified as PASS. Real NSIS remains BLOCKED.
