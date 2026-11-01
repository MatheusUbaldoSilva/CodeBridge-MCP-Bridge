# RAG-DEL 01.04 DQ-E-F-14 - Pipe ACE policy review (DEV, 2026-11-01)

## Purpose
Extend the prior G18 read-only Win32 ACE metadata inventory with a pure
DEV policy review of **caller-supplied G18-shaped records**. No real Windows
handle, installed process, token, ACL or IPC endpoint is queried. The
review intentionally remains conservative and permanently blocks
operational deletion.

## Implementation
- rag/runtime/knowledge_deletion_pipe_acl_policy_review_dev.py
- Requires read_only=true and *all* prior G18 operational/attestation
  flags false; rejects attempts to force trusted or authorized claims.
- Requires bounded <=64 entries with exact allow/deny ACE fields,
  lowercase 8-character hexadecimal access masks, 64-character
  SHA-256 SID receipts, classified principals and consistent item count.
- Flags any ALLOW ACE for G18's eleven well-known broad principal
  classes regardless of mask. This is a conservative diagnostic rule,
  **not a calculation of effective access rights**.
- Notes that OTHER_PRINCIPAL sid_sha256 cannot be mapped to an
  authorized installed peer or token; a private-looking list is not proof.
- Rejects unsupported/unknown ACE types and incomplete/failed inventory.
- The returned record omits SID hashes and never authorizes pilot,
  deletion, privilege changes, publication or installation.

## Limitations
The trusted caller, OS AccessCheck, deny ACE ordering, inherited/conditional
ACE evaluation, restricted tokens, actual SID/session ownership, child
handle inheritance and effective impersonation are **NOT verified**.
Input can be forged. G32 platform block is respected.
There is no production pipe inspection or bypass.

## Tests
12 pure-function tests cover broad principal classes, deny-only
scenarios, mismatched item counts, malformed masks/types/SIDs,
forged flags, zero/overflow, no mutations and no hashes in results.

## Next gate
Any real installed Windows IPC channel would require explicit
operator-approved cooperative instrumentation, independently trusted
OS identity checks and effective access evaluation. This phase does
not implement or authorize that integration.

## Verified
- Focused F-13/F-14: 25 PASS.
- RAG-DEL: 708 tests (702 PASS, 6 SKIP, 0 FAIL).
- RAG-AUTO non-MCP: 241 tests (236 PASS, 5 SKIP, 0 FAIL).
- MCP: 12 PASS.
- Aggregate: 961 tests, 950 PASS, 11 SKIP, 0 FAIL.
- No installed GUI, queue, real index, Stable or GitHub changes.
