# P9-B real NSIS recovery journal tamper rejection
Date: 2026-10-23
Status: isolated adversarial test PASS; P9-B OPEN

Added a negative test extending the genuine NSIS interrupted installation scenario. The independent rollback process exits hard after applying shell recovery. A separate process then tries to resume from a journal deliberately appended with malformed JSON.
The resumed recovery fails closed before mutation, returns exit 2 / DETACHED_EXCEPTION, and preserves the postcrash installed-file bytes.
The test uses only disposable file roots and remapped genuine HKCU keys, never CodeBridge production state.
Evidence: test_actual_nsis_crash_corrupt_journal_refuses_replay PASS. Remaining production authorization gates unchanged.