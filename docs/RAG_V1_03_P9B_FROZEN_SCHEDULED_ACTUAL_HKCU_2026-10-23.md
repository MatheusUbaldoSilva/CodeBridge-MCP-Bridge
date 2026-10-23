# P9-B ? frozen independent source with actual isolated HKCU tests

Date: 2026-10-23
State: SCHEDULED FROZEN-SOURCE HKCU LAB VERIFIED; P9-B OPEN.

Source was frozen from Git HEAD 047686949eb7 at staging
P9B_DETACHED_SOURCE_047686949eb7, not imported from the live
CodeBridge repository. Test process ran with Python isolated mode.

An independent Windows Scheduled Task CodeBridge_P9B_FrozenHKCU
ran the scoped real HKCU + combined file/shortcut integration
test file test_rag_p9b_combined_actual_hkcu_integration.py.

Persisted attestation frozen_hkcu_result.json:
- FROZEN_HKCU_SCHEDULED_VERIFIED
- 6 tests, zero errors, zero failures
- ancestry_verified true
- production_modified false

HKCU keys were remapped to unique disposable test subkeys using
ScopedHKCU. CodeBridge production registry keys were not changed.
Temporary scheduled task and worker script were removed afterward.

This is stronger evidence of code-source isolation than running
tests from the development checkout, but it does not yet prove
independently controlled real NSIS execution, durable supervisor
restart, installed-file rollback, or postupdate public CBMCP/1
reconnection. These are required before P9-B can close.
