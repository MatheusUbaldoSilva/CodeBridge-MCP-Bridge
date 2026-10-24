# P9-B.02-C — Verify config identity immediately before worker and after worker
Date: 2026-10-24. Status: isolated lab PASS; P9-B OPEN.

The bounded disposable combined recovery adapter now rechecks the frozen-by-hash configuration bytes immediately before invoking the combined recovery worker and immediately after its return. If the config changes during execution, or disappears, terminal certification is refused; reserved retry remains durable for manual/supervisor review. Added two negative tests: in-worker mutation and in-worker unlink both fail closed without TERMINAL.

This is detection around a mutable file, NOT a trusted frozen file descriptor, filesystem immutability, cryptographic publisher authentication, or permission for official deployment. Full P9B regression 602 tests PASS in 73.431s. Independent trust root, real unified NSIS one-journal transaction and autonomous scheduled genuine rollback are still unproven.