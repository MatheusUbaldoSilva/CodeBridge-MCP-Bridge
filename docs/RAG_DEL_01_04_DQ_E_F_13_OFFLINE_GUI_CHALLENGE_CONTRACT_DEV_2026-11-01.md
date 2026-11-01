# RAG-DEL 01.04 DQ-E-F-13 - Offline GUI challenge/response contract (DEV, 2026-11-01)

## Objective
Develop and adversarially test a bounded HMAC-based diagnostic challenge
protocol **only between simulated peers in a DEV Python lab**.
This does NOT create an authenticated IPC channel to an installed GUI.
The caller supplies the lab secret; neither that shared secret nor any
test HMAC establishes the identity or loaded code of a live process.

## Source
- rag/runtime/knowledge_deletion_gui_challenge_contract_dev.py
- make_offline_gui_challenge_dev(): random 256-bit nonce, exact lowercase
  SHA-256 snapshot and loaded-code labels, exact PID and process birth,
  issued time, max 10-second expiry.
- make_mock_gui_response_dev(): test-only HMAC-SHA256 over canonical
  challenge using a test-domain prefix. No actual process is contacted.
- review_mock_gui_response_dev(): strict challenge-response structure,
  rejects altered source/PID/birth/code/nonce, bad MAC, expired/future
  times and replays in a caller-owned in-memory test set.
- Challenge and response fields never include operational authorization
  grants. Every result hardcodes installed_gui_attested=false,
  ready_for_operational_pilot=false, activation_authorized=false,
  operational_use_allowed=false, read_only=true.

## Security limitations
This phase is a MOCK PROTOCOL only. No OS-bound process identity,
trusted key provisioning, installed loaded-code proof, secure channel
permissions, audited peer ACL, persistent replay ledger or GUI installation.
All true mock checks demonstrate only internal contract correctness,
not production trust. Operational G32 block remains; no attempt to bypass.

## Verification
13 direct adversarial tests cover successful mock; expiry and future
time; replay; nonce uniqueness; HMAC tampering; binding mismatch; forged
operational fields; invalid inputs; and no consumption of failed nonces.
Do not merge with installed/Stable or enable deletion without separately
approved integration and explicit operator queue/journal audit.

## Verified results
- F-13 direct: 13 PASS.
- Full RAG-DEL: 696 tests, 690 PASS / 6 SKIP / 0 FAIL.
- RAG-AUTO non-MCP: 241 tests, 236 PASS / 5 SKIP / 0 FAIL.
- MCP: 12 PASS.
- Total: 949 tests, 938 PASS / 11 SKIP / 0 FAIL.
- Installed GUI untouched, no production queue/index mutation, no GitHub push.
