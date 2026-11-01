# RAG-DEL 01.04 DQ-E-F-12 - Coherent GUI evidence package (DEV, 2026-11-01)

## Objective
Make the relationship between F-8/F-11 exact GUI/MCP argv, F-10 process
birth-order metadata, and F-7/F-9 offscreen-loaded GUI code observable
and reproducible from **the same caller-supplied process snapshot**.

This phase does not open a trusted IPC channel, inspect a live installed
GUI interpreter, mutate a RAG catalog, authorize deletion or establish
actual process identity. Snapshot hash is **not a MAC/signature** and cannot
prove provenance, origin or freshness without independent trusted evidence.

## Implementation
- Added rag/runtime/knowledge_deletion_gui_evidence_package_dev.py.
- A bounded process metadata snapshot of up to 64 records is canonicalized
  by PID; the receipt includes PID, parent PID, creation epoch in milliseconds
  and Windows command-line text (not exported to the result).
- Fail closed on malformed PID/PPID, creation values, duplicate PIDs,
  missing/oversize command lines, NUL, non-absolute repo root or invalid
  prior receipt. Extra caller flags are excluded from the receipt.
- Both F-8/F-11 and F-10 independently evaluate **the same input list**.
  F-9 evaluates the separate offscreen GUI observation.
- An optional prior SHA-256 comparison only detects that caller-supplied
  metadata has changed. A matching digest does NOT authenticate metadata.
- Even when all DEV observations are positive, report
  F12_DEV_SNAPSHOT_COHERENT_INSTALLED_UNVERIFIED and preserve blocking
  installed-GUI trusted-channel, PID/birth, loaded-code, effective IPC
  ACL/token and operator queue/journal gates.
- Every response has installed_gui_attested=false,
  ready_for_operational_pilot=false, activation_authorized=false,
  operational_use_allowed=false and read_only=true.

## Test coverage
16 focused tests simulate positive source-only coherence; deterministic
ordering; changed argv/birth; forged approval flags; stale receipt;
invalid inputs; process parent/creation failures; F-11 CLI-shadowing;
no caller mutations; and no raw argv exposure.

## Read-only DEV observation
Existing CodeBridge launcher/GUI/MCP: five Windows CIM process records.
F-8/F-11 exact argv true; F-10 birth chronology true; PySide6 **separate
offscreen process lab** loaded-reader observations true.
Snapshot receipt: bae856fbc53246dcc86a8678d659dae6586b9bddfd58df423b7d4e38015a895c
State: F12_DEV_SNAPSHOT_COHERENT_INSTALLED_UNVERIFIED.
Installed GUI attested: false. Deletion activation authorized: false.

The separate offscreen process is NOT the installed GUI. Do not infer
production deployment readiness from any of these observations.

## Approval gates and scope
The installed GUI would need a separately authorized cooperative,
authenticated in-process response tied to actual process identity and
loaded reader code. Effective Windows IPC access isolation and an
explicitly authorized queue/journal review remain required. Prior G32
platform security restriction remains in force; no bypass attempt.
Do not touch Stable, installed GUI/MCP, operational queue, real index
or GitHub without explicit separate authorization.

Only two NEW files in this phase: DEV-only module and focused tests,
plus this patch note. The five preexisting dirty files remain untouched.

## Regression verification, 2026-11-01
- F-12 direct F-8/F-9/F-10/F-12 tests: 53 PASS, 0 FAIL.
- RAG-DEL entire suite: 683 tests, 677 PASS, 6 SKIP, 0 FAIL.
- RAG-AUTO non-MCP suite: 241 tests, 236 PASS, 5 SKIP, 0 FAIL.
- MCP-only suite: 12 PASS, 0 FAIL.
- Total: 936 tests, 925 PASS, 11 SKIP, 0 FAIL.
- Qt font directory warning remained non-fatal.
- No installed GUI code proof, no operational action, and all deletion gates false.
