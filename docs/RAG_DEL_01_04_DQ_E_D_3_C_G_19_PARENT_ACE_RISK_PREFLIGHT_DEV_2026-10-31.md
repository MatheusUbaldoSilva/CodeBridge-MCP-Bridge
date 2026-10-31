# RAG-DEL-01.04 DQ-E-D-3C-G-19 — Lab pipe ACE risk preflight

The existing scratch-only HMAC parent now inventories simple Windows ALLOW/DENY ACEs on all three local pipe handles BEFORE transmitting any secret. It refuses the transaction if GetAclInformation/GetAce cannot observe a DACL, if ACE type is unsupported, if a known broad principal receives an ALLOW entry, or if ACE inventory is malformed or empty. The failure path reaps the child and closes every pipe descriptor.

Seven G-19 tests PASS, including simulated Everyone ALLOW, unknown ACE type, missing DACL, malformed count and truncated inventory. A real scratch worker roundtrip remains functional. Combined tests for G-15/G-18/G-19 pass without ResourceWarning.

THIS IS NOT effective ACL policy validation: unclassified trustees are allowed through this scratch experiment, and Windows token rights, HANDLE duplication, other inherited handles, and production principals have NOT been authenticated. All operational permission flags remain false and deletion is still blocked. No installed services, real queues/indices, Stable, or GitHub push altered.
