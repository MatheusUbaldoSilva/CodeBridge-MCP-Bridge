# P9-B ? frozen, separately scheduled recovery source test

Date: 2026-10-23
Status: INDEPENDENT SOURCE LOAD AND LAB TESTS VERIFIED / P9-B OPEN

CodeBridge source HEAD 047686949eb7 was archived using git archive
limited to installer/ and tests/, with no untracked local files.
Archive SHA256:
01434E7D2D1358162E43BD4F97B463092A6C5D934A1D53CFDAAE832B365856B0

The frozen source tree was extracted beneath
LOCALAPPDATA/CodeBridge-MCP-Bridge/release_staging/
P9B_DETACHED_SOURCE_047686949eb7 (526 files).

Using Python -I (isolated mode) from outside the repository,
35 journal and external recovery tests passed, with imports
confirmed to originate within the frozen staging tree.

A separate disposable Windows Scheduled Task
CodeBridge_P9B_FrozenEvidence then ran those 35 tests directly
from the frozen source tree, using the staged psutil dependency.
Process ancestry was confirmed disjoint from the installed CodeBridge.

Persisted attestation:
- state: FROZEN_SOURCE_SCHEDULED_VERIFIED
- tests: 35
- failures: 0
- errors: 0
- ancestry_verified: true
- production_modified: false
- verified: true

Evidence is at staging/P9B_DETACHED_SOURCE_047686949eb7/
attestation_result.json. The scheduled task and temporary
worker script were removed after the run.

This proves independent execution of the frozen source for
read-only/disposable recovery tests, not that a mutating external
supervisor could recover a failed NSIS update in production.
The earlier real isolated HKCU API tests and 236-file snapshot-backed
disposable recovery remain separate evidence; do not combine them
into a false production cutover claim.

No production NSIS execution, MCP shutdown, live HKCU changes or
RAG index modification occurred. P9-B remains OPEN.
