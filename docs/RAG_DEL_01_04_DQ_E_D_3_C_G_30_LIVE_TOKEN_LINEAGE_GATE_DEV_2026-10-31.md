# RAG-DEL-01.04 DQ-E-D-3C-G-30 — Token-lineage gate on live cross-process scratch HMAC

Integrated the G-29 read-only Win32 child OpenProcessToken query into the existing G-28 authenticated native same-end handle handshake, BEFORE ACK. The parent refuses if TokenUser/TokenIsAppContainer cannot be queried from the spawned child held process HANDLE; the cleanup kills/reaps the child and closes six scratch pipe descriptors. It now returns only the boolean relationship parent_child_account_sid_equal and child_appcontainer, without exposing raw user SID, secrets or token handles.

Three new tests PASS: real worker same SID, simulated token-query failure with child reaping, and a deliberately forged 'isolated' token evidence object that still cannot switch on operational access. The scratch Python child typically runs with the same account SID and is not AppContainer, so we explicitly DO NOT assert effective token isolation.

This is a safety review, NOT deployment-ready privilege boundary or AccessCheck verification. Still no installed CodeBridge GUI, real worker inference path, live queue/index, Stable or GitHub mutation. Deletion remains blocked.
