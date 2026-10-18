# RAG-LAB.04 - Report integrity patch notes (2026-10-18)
Scope: disposable fixture only; no production backup or shutdown.
17a045e: offline_fixture_snapshot.py and test_offline_lab04_snapshot_report_race.py. Reject report.json changed after write (RED/GREEN).
444df6b: offline_fixture_snapshot.py and test_offline_lab04_snapshot_report_hardlink.py. Reject same-content external report hardlink, st_nlink must be 1 (RED/GREEN).
aff3707: offline_fixture_restore.py and test_offline_lab04_restore_report_hardlink.py. Reject source report replaced by hardlink after validation (RED/GREEN).
Regression: 400 backend PASS (272 offline + 83 generation + 7 preflight + 38 incremental), 0 failures. Commits pushed and staged diff audited.
RAG-LAB.04 normative PARTIAL: native Qdrant Server snapshots not tested. Qt PySide6 unavailable. TOCTOU checks do not prove global quiescence.
production_backup=BLOCKED; all_handles_closed=false; production_quiescence_proven=false.

2bbac58: offline_restore_equivalence.py and test_offline_lab04_equivalence_report_hardlink.py. Reject external same-content hardlink substituted during independent restore audit (RED/GREEN).
Focused LAB04 regression on 2026-10-18: 43 tests PASS (exit 0).
Full backend regression recorded at 2bbac58: 401 PASS (273 offline + 83 generation + 7 preflight + 38 incremental).
RAG-LAB.04 remains PARTIAL: native Qdrant Server snapshots and global handles/mmap quiescence unproven; production backup remains BLOCKED.

RAG-LAB.04 - generation-state metadata invariant (2026-10-18)
Files: rag/runtime/offline_fixture_restore.py; rag/runtime/offline_restore_equivalence.py; tests/test_offline_lab04_report_generation_flag.py.
A synthetic report with active_generation_changed=true was previously accepted by both restore and independent equivalence; two negative tests reproduced the defect (RED, 2 failures).
Both paths now require active_generation_changed is exactly false, matching the original capture report contract (GREEN, 2 tests).
Regression: focused RAG-LAB.04 45 PASS; backend 403 PASS (275 offline + 83 generation + 7 preflight + 38 incremental).
Synthetic fixture only; no production backups, process shutdown, live index operations or production permissions.
RAG-LAB.04 remains PARTIAL; native Qdrant Server snapshots, global Windows handles/mmap, production quiescence and go-live are NOT proven.
production_backup=BLOCKED; copy_authorized=false; production_quiescence_proven=false.

RAG-LAB.04 - restore-parent directory swap (2026-10-18)
Files: rag/runtime/offline_fixture_restore.py and tests/test_offline_lab04_restore_parent_swap.py.
RED: in a disposable Windows fixture, replace offline-fixture-restores with a directory symlink after copy validation; old restore published the snapshot outside the fixture root.
GREEN: recheck destination parent, staging, destination and ancestors before publication; avoid deleting a staging directory through a redirected ancestor in cleanup.
Focused LAB04: 46 PASS; backend regression: 404 PASS (276 offline + 83 generation + 7 preflight + 38 incremental).
No guarantee of atomic Windows-wide quiescence against adversarial post-check swaps; real maintenance, Qdrant Server snapshots and production backups remain BLOCKED.
