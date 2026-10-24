# P9-B — Fix process race in persistent OS lock initialization
Date: 2026-10-24
Status: PASS in isolated Windows regression; P9-B still OPEN.

Problem: two independent processes raced between an xb-created .lock file and its initial one-byte fsync. The old reader checked lock.stat().st_size before acquiring the OS lock and could transiently refuse a valid newly created zero-byte sidecar as JOURNAL_LOCK_PATH_INVALID; a retry reservation then lacked an attempt. This is a plausible diagnosis of prior sporadic two-process retry tests, not conclusive forensic proof of every observed failure.

Fix: perform initialization and validation under the same persistent OS byte-range lock. Creator opens x+b and initializes byte 1 only while holding the OS lock; existing opener waits for the lock before checking exact b'1' and file length. Preserve persistent sidecar, refusal on pre-existing empty/tampered sidecars, and local advisory trust limitations. No official registry or application files modified.

Tests: 21 focused journal lock+ledger tests PASS (includes two new empty/tampered lock negatives); 18 consecutive independent two-process retry tests PASS; P9B full 595 tests PASS in 64.569s. Remaining: full power-loss persistence/parent directory fsync, independent protected trust root, unified NSIS transaction and supervisor automatic recovery certification. No P9B macro-phase closure claimed.