# P9-B.03 — Scheduled Python worker boot root-cause and scoped diagnostic
Date 2026-10-24.
Status: Minimal automatic Windows Scheduled Task Python boot fixed and independently observed, NOT genuine full rollback supervisor recovery. P9-B OPEN.

After the first full scoped-HKCU periodic rollback attempt failed INITIAL_RECOVERY_ATTEMPT_NOT_OBSERVED (185s), a scratch-only boot diagnostic exposed that the Scheduled Task ran the Python process, but importing installer.rag_p9b_scheduled_combined_retry_adapter failed with ModuleNotFoundError: No module named 'installer'. A scheduled script in TEMP does not automatically add the repo's working directory to Python sys.path. The diagnostic worker now explicitly inserts the verified current repository path before import. A true independently scheduled -Once trigger then returned SCHEDULED_PYTHON_IMPORT_CONFIRMED, boot_exists=true, import_exists=true, error_exists=false. Repeated run confirmed the same. Real scratch task and TEMP files were cleaned between tests.

An additional actual scheduled combined-HKCU attempt with explicit sys.path still failed INITIAL_RECOVERY_ATTEMPT_NOT_OBSERVED after 187.553s; this shows at least one further boot/launch/invocation gap, not a completed scheduled recovery. That unverified long integration test was removed rather than being committed or counted. All disposable task names confirmed absent after cleanup. No production files/HKCU/RAG modified.

Reusable script installer/p9b_scheduled_python_boot_diagnostic_lab.ps1 has a bounded 90-observation task, internal boot and import/error markers, fails closed if no import, and always unregisters its TEMP task in finally. Four fast syntax/contract tests in tests/test_rag_p9b_scheduled_python_boot_diagnostic_contract.py PASS.

Next: collect first-process boot marker and TaskScheduler.LastTaskResult from the ACTUAL combined worker before testing 3-minute repetition. Persist a bounded error transcript in an isolated folder until it is read, then cleanup. Determine difference between standalone successful boot and combined worker invocation. Do not attribute success to initial schedule registration alone, and never enable system-wide event logging without operator approval.

Independently protected root P9-B.01-C and one NSIS update/rollback journal P9-B.02-C/E remain missing. No official cutover authorized.