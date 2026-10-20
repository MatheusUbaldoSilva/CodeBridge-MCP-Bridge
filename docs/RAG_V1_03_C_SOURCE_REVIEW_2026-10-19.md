# RAG V1.03-C - Immutable candidate content-review evidence

**Status: PENDING HUMAN REVIEW. NO PUBLICATION AUTHORIZATION.**

- Baseline: v1_base_6142ab6e3b534f (210 indexed sources).
- New candidate: v1_delta_bebee8b8a49943 (211 indexed sources and 8,778 independently verified vectors).
- Manifest difference: 1 ADDED, 5 MODIFIED, 0 REMOVED, 205 UNCHANGED.
- Source freshness: SOURCE_SNAPSHOT_CURRENT, 121 byte-exact and 90 newline-only, 0 stale.
- Evidence SHA-256 (not a signature or permission): b8757eb7f10b32ac1728ff10dfb4fd54f352d5b691ac7a88bb26262a57418e2c
- Method: READ-ONLY comparison of indexed SQLite document content with versioned manifest SHA; each indexed content hash is revalidated.
- Diff statistics and line ranges are navigation aids only; they do not replace review of the actual source changes.

## File-by-file scope

| Source | Action | Lines added/removed | Chunks old/new | Change hunks |
|---|---|---:|---:|---:|
| rag/runtime/live_integrity.py | ADDED | +159/-0 | 0/6 | 1 |
| author_mcp/mcp_server.py | MODIFIED | +82/-0 | 48/52 | 4 |
| author_mcp/rag_bridge.py | MODIFIED | +340/-20 | 10/17 | 7 |
| rag/runtime/production_index.py | MODIFIED | +11/-1 | 5/5 | 1 |
| rag/runtime/production_search.py | MODIFIED | +57/-26 | 5/5 | 17 |
| rag/runtime/status.py | MODIFIED | +20/-15 | 17/17 | 3 |

## Indexed content SHA-256 and candidate line ranges

### rag/runtime/live_integrity.py

- Action: ADDED; indexed lines 0/159.
- Old SHA-256: NOT_PREVIOUSLY_INDEXED
- Candidate SHA-256: cea260ba08b77d5ed30e54aacea63de33aca09e20818fdb6cc577735a3e8361d
- Candidate line ranges (up to 20): 1-159
- Human-reviewed: NO.

### author_mcp/mcp_server.py

- Action: MODIFIED; indexed lines 1535/1617.
- Old SHA-256: 72ccdaff8b7c53a5b1aa29a7d3bb4ad4db9c6776b4f1ff7869040fc8d55a7d2d
- Candidate SHA-256: 3e336ddec307cf97daaf13ba028410a19b50cb0f70fb51affc7cdfa8b3bc5646
- Candidate line ranges (up to 20): 15-15, 51-67, 300-302, 740-800
- Human-reviewed: NO.

### author_mcp/rag_bridge.py

- Action: MODIFIED; indexed lines 152/472.
- Old SHA-256: e8cf800895c4bd9dfcbd3bcde2e74fa4eba166c6fb4bcb0f6510d74671d2539c
- Candidate SHA-256: e4020082a09a7658f2905550c7e79fbd9f391093975406ddb18d0612286ced85
- Candidate line ranges (up to 20): 62-191, 204-265, 270-276, 288-306, 321-372, 388-431, 446-471
- Human-reviewed: NO.

### rag/runtime/production_index.py

- Action: MODIFIED; indexed lines 151/161.
- Old SHA-256: 184f893b0442b2b93f6b403d5bf460c12ef439fa3407ffcde0c82ca931c74b08
- Candidate SHA-256: 43cd1d969579901c0bbb5be2a983d891d1611ea44199814e5bbd3cc54d2bc25c
- Candidate line ranges (up to 20): 96-106
- Human-reviewed: NO.

### rag/runtime/production_search.py

- Action: MODIFIED; indexed lines 115/146.
- Old SHA-256: fa75d158306ec08fdbaccf0d59824e75beb5d581af5398de266b9473e10f5c6a
- Candidate SHA-256: d5f16b29c89b5fc725dca07de95fc8b7f596272b9adbdf2936e2fe59ea170340
- Candidate line ranges (up to 20): 25-25, 29-30, 32-32, 42-44, 48-50, 52-52, 54-54, 58-60, 64-68, 70-70, 74-74, 82-85, 93-114, 121-123, 131-132, 135-135, 137-139
- Human-reviewed: NO.

### rag/runtime/status.py

- Action: MODIFIED; indexed lines 411/416.
- Old SHA-256: 396e5ba04b08b1eb696769d5347dda25db4f63c1f9b854899312699bc549563e
- Candidate SHA-256: 982114d50888575d2c096f9f79739a00cb94ec6497fc0a1bdb3e9cd29575803e
- Candidate line ranges (up to 20): 328-328, 330-346, 394-395
- Human-reviewed: NO.

## Required gate evidence

- [ ] Review complete diff for all 5 modified and 1 newly indexed source.
- [ ] Approve exact source paths and SHA-256 after inspecting source changes.
- [ ] Restart the CodeBridge GUI externally; run the public MCP 3/3 concurrent HYBRID probe without fallback.
- [ ] Perform a separately approved supervised cutover with reader lock and durable journal proof.
- [ ] Prove public retrieval and supervised rollback with the new generation; retain old generation and recovery evidence.

**Production state at report creation: legacy active; no active-generation pointer or pending journal.**
**This report has no approval flag and cannot activate the candidate.**
