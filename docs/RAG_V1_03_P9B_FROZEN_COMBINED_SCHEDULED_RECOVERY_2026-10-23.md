# P9-B ? combined scheduled recovery from frozen source

Date: 2026-10-23
Status: LAB PASSED / PRODUCTION CUTOVER NOT CERTIFIED

Git-frozen installer and tests from source commit 047686949eb7
were staged outside the development repository. A temporary
independent Windows Scheduled Task CodeBridge_P9B_FrozenCombined
executed a dedicated Python worker importing those staged modules.
Process ancestry was verified outside the installed CodeBridge.

Persisted frozen_combined_result.json:
- state: FROZEN_COMBINED_SCHEDULED_VERIFIED
- verified: true; ancestry_verified: true
- hkcu_tests: 6 (ScopedHKCU remapped real winreg calls)
- old_files_checked: 236
- new_targets_removed: 22
- shortcuts_checked: 5
- fake_registry_keys_checked: 2
- production_modified: false

In the same independent worker the real installed-file preimage
P9B_FILE_ROLLBACK_b3e5e5e42e5f.zip populated a disposable
TemporaryDirectory. A separate subprocess intentionally exited 83,
then a recovery subprocess returned 0 and restored the 236 archived
files, removed 22 new targets, and verified five shortcut and two
simulated-registry fixtures. Six real Windows HKCU-isolated integration
tests were also executed independently within that worker.

These are sequential tests within one independent worker, not one
atomic update-and-rollback transaction. The real HKCU operations were
confined to unique remapped laboratory keys; the snapshot recovery
used simulated HKCU. No NSIS installer was launched, no production
registry keys or installed files were modified, and the MCP/RAG
public service was not stopped. Temporary task, worker and disposable
installation folders were verified absent after completion.

P9-B remains OPEN. Missing: production-grade independent mutation
control, durable crash-restart for an actual NSIS installation,
full real HKCU/shortcut rollback and public CBMCP/1 re-handshake.
