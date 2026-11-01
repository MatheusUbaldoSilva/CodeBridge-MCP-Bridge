# RAG-DEL CLOSE-03 — Scratch connected peer effective token AccessCheck

Date: 2026-11-01. Branch: dev-local.

## What was added

- `rag/runtime/knowledge_deletion_scratch_peer_acl_dev.py`
  obtains actual scratch-client PID and creation receipt from the kernel,
  reads the *real connected scratch server pipe's* kernel security descriptor,
  opens the peer PROCESS token, duplicates it as an impersonation token
  (without impersonating the current server thread), and invokes native
  Windows AccessCheck with the file/pipe generic mapping.
- Existing cross-process scratch tests now verify:
  1. Real child peer PID, birth, user token and kernel DACL access for read data.
  2. Spoofed client-reported PID is rejected *before* AccessCheck.
  3. Spoofed process creation receipt is rejected *before* AccessCheck.
  4. Invalid peer PID input is rejected.
- Security descriptor needs OWNER, GROUP and DACL for AccessCheck; missing
  GROUP caused Win32 error 1338 and was fixed before acceptance.

## Scope

This is a disposable independent `CB.RAGDEL.PEER.<uuid>` Named Pipe only.
No installed GUI loaded-code identity, actual installed operational IPC token
or production effective ACL was inspected. It does not permit deletion.
All results hard-code `activation_authorized=False`,
`operational_use_allowed=False`, `installed_peer_token_attested=False`.
The real GUI remains locked, and G32/CLOSE-03 stays BLOCKED.

## Reconciliation

One existing READY_FOR_REVIEW job / one CANARY_ACTIVE for newworldpvp is
preserved. The operator decision record is in
`docs/RAG_DEL_CLOSE03_CANARY_OPERATOR_DECISION_2026-11-01.md`.
The public RAG generation has not been switched; no queue, catalog, journal,
ACL, installed binary or GitHub/Stable writes.
