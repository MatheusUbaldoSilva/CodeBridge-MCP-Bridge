# P9-B exact Scheduled Task test count and skip gate
Date: 2026-10-23
Status: disposable scheduled lab PASS, P9-B OPEN

The independent task now records unittest skipped and unexpectedSuccesses counts and requires exactly seven completed tests, zero failures, zero errors, zero skips, and zero unexpected successes. A skipped NSIS case cannot silently count toward certification on a host without the Windows tooling. The proof remains fail-closed with diagnostic details.

Files: installer/p9b_scheduled_combined_lab.ps1; tests/test_rag_p9b_scheduled_combined_lab.py.
Validation: 2 schedule contract tests PASS and an actual Windows Scheduled Task run returns SCHEDULED_COMBINED_LAB_VERIFIED with exactly 7 tests, ancestry_verified true, production_modified false and production_nsis_executed false.

This is a genuine NSIS build executed only by child tests inside a disposable lab. Production transaction and recovery remain unapproved.