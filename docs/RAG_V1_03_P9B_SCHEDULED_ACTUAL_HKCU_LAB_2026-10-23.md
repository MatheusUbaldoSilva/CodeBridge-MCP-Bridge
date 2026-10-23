# P9-B ? independent scheduled real HKCU isolated lab

Date: 2026-10-23
State: DISPOSABLE REAL HKCU API LAB PASS / P9-B OPEN

A disposable Windows Scheduled Task CodeBridge_P9B_ActualHKCU_Disposable
executed tests/test_rag_p9b_combined_actual_hkcu_integration.py
in a separate Python process under the active Windows user.
Process ancestry was verified by inspect_detached_process_ancestry
outside the CodeBridge MCP process tree.

Observed result:
- state: SCHEDULED_ACTUAL_HKCU_LAB_VERIFIED
- ancestry_verified: true
- verified: true
- tests: 6
- errors: 0
- failures: 0
- production_modified: false

The test suite invokes the real Windows HKCU registry API but uses the
existing ScopedHKCU adapter that remaps keys to unique throwaway
laboratory subkeys. Combined file/shortcut recovery and refusal behavior
were exercised on disposable fixtures, not CodeBridge production keys.

After completion the scheduled task was unregistered and the temporary
worker directories were absent. The three historical local dirty files
were left untouched. No real NSIS installer executed, no live MCP shut
down, and no RAG public index changed.

This is NOT certification of a full live update or of a durable
production mutating supervisor. P9-B remains OPEN pending a
restartable independently supervised NSIS transaction with verified
rollback, then authorized cutover and CBMCP/1 queue/scheduler/RAG
reconnection evidence.
