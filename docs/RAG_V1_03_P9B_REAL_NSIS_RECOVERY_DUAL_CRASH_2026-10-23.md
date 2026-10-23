# P9-B genuine isolated NSIS recovery crash at both boundaries

Date: 2026-10-23
State: ISOLATED LAB PASSED; P9-B OPEN

The genuine NSIS isolated 258-target test now also covers interruption of the independent recovery process:
- before journaled completion of file rollback (intentional os._exit(87))
- after shell rollback has been applied and before its own completion can be journaled (intentional os._exit(88))

In each case a new separate recoverer reads the persisted journal, restores all 236 prior installed file payloads and removes 22 newly written targets, validates 5 lab shortcuts and 2 true Windows HKCU remapped keys, and records final verified recovery.
The unchanged normal NSIS interruption path remains a separate regression.
Results: 3 real Windows NSIS interrupted chain tests PASS.

This uses a deliberately generated lab NSIS build in a disposable path, not the official CodeBridge installer. No active production installation, registry key or public RAG index was modified and no public MCP shutdown or reconnect was attempted.
Next gate: independent scheduled durable update transaction binding identity and actual official NSIS before operator-authorized cutover.