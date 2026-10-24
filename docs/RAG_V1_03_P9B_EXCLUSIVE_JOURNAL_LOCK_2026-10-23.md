# P9-B exclusive durable journal lock
Date: 2026-10-23
Status: isolated tests PASS, P9-B remains OPEN

Changes since 6e0e22f:
- 8df13e4: deny stale append attempts on unexpectedly advanced/corrupted rollback journal
- fd833b2: implement OS-exclusivity with persistent sidecar: Windows msvcrt byte-range lock and POSIX flock; recheck journal before fsync append under lock
- 1cb2583: prove lock is released after child process hard exit 91
- b4381ac: run detached launcher hard-exit survival within Windows Scheduled Task, eight real isolated recovery test cases passed
- Current increment: prove an already blocked waiter resumes when the lock owner hard-exits with code 92

Evidence: 6 exclusive-lock cases PASS and full P9B suite 513 tests PASS in 50.231s. Earlier scheduled supervisor run SCHEDULED_COMBINED_LAB_VERIFIED, 8 tests, ancestry verified, production_modified false.

Scope limit: advisory same-host locking protects cooperating writers against interleaved append, but it is not an ACL-enforced trusted transaction manifest, independently restarting scheduler or production-grade atomic updater. No CodeBridge installed files, real public registry keys, running MCP, or RAG index were changed.