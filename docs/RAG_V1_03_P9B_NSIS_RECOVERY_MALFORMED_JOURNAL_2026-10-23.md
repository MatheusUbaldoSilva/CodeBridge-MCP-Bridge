# P9-B - NSIS isolated recovery refuses malformed journal

Date: 2026-10-23
Status: incremental safety improvement only; P9-B OPEN

## Change
- installer/rag_p9b_real_nsis_interrupt_lab.py
  - Reads the isolated journal with explicit file and link checks
  - Rejects unreadable, invalid JSON and non-object journal payloads before mutation
  - Verifies exactly one event and matching laboratory identity
- tests/test_rag_p9b_real_nsis_interrupt_lab.py
  - Adds malformed JSON rejection without file mutation
  - Adds non-object JSON rejection without file mutation

## Verification
- 6 dedicated recovery tests PASS
- 35 focused NSIS, journal and independent-supervisor tests PASS
- Python compilation PASS
- git diff --check PASS

## Safety boundary
- No production NSIS execution
- No modification of installed CodeBridge, registry or public RAG index
- Does not prove one durable atomic transaction across files, shortcuts and HKCU
- Three preexisting local dirty files remain protected and uncommitted
- Continue P9-B with one supervised, externally persistent isolated transaction and crash-restart evidence before any operator-approved cutover