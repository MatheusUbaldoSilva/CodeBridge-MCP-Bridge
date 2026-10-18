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

RAG-LAB.04 - snapshot-parent directory swap (2026-10-18)
Files: rag/runtime/offline_fixture_snapshot.py and tests/test_offline_lab04_snapshot_parent_swap.py.
RED: in a disposable Windows fixture, replace offline-fixture-backups with a symlink after source verification; old snapshot published outside its fixture root.
GREEN: reject redirected backup parent, staging, target or their ancestors immediately before snapshot publication and avoid deleting staging through a redirected parent during cleanup.
Focused LAB04: 47 PASS; backend regression: 405 PASS (277 offline + 83 generation + 7 preflight + 38 incremental).
Synthetic laboratory only; production quiescence, native Qdrant Server snapshots, and real backup remain BLOCKED.

RAG-LAB.04 - duplicate JSON keys in snapshot reports (2026-10-18)
Files: rag/runtime/offline_fixture_report.py (strict shared decoder), offline_fixture_restore.py, offline_restore_equivalence.py, tests/test_offline_lab04_report_duplicate_keys.py.
RED: a snapshot report with duplicate production_authorized keys and identical false values was accepted for both synthetic restore and independent audit (2 tests failed).
GREEN: strict JSON object_pairs_hook now rejects duplicate keys at every nesting level; root must be an object. Both restore and independent audit use this decoder.
Regression: RAG-LAB.04 focused 49 PASS; backend 407 PASS (279 offline + 83 generation + 7 preflight + 38 incremental).
Synthetic lab only. Backup and go-live remain BLOCKED; native Qdrant Server and global quiescence not proven.

RAG-LAB.04 - non-finite JSON numbers (2026-10-18)
Files: rag/runtime/offline_fixture_report.py and tests/test_offline_lab04_report_nonfinite.py.
RED: report containing NaN with otherwise valid synthetic metadata passed both restore and independent audit. Python also accepted NaN, Infinity, and -Infinity in strict report decoder.
GREEN: strict report parser uses parse_constant to reject non-standard non-finite numbers; 3 focused tests pass.
Regression: RAG-LAB.04 focused 52 PASS; backend 410 PASS (282 offline + 83 generation + 7 preflight + 38 incremental).
No production backup or process shutdown. RAG-LAB.04 remains PARTIAL; native Qdrant Server and global quiescence unproven; production backup BLOCKED.

RAG-LAB.04 - independent-audit saved-directory reparse swap (2026-10-18)
Files: rag/runtime/offline_restore_equivalence.py and tests/test_offline_lab04_equivalence_parent_swap.py.
RED: after second cross-store semantic validation, replacing saved backup directory with a symlink to the exact same directory outside the allowed fixture left independent audit in a non-BLOCKED lab state.
GREEN: independent auditor rechecks saved, original, restored, report and ancestor directory redirections after semantic validation; reject on any reparse redirection.
Regression: RAG-LAB.04 focused 53 PASS; backend 411 PASS (283 offline + 83 generation + 7 preflight + 38 incremental).
This is defense-in-depth, not atomic global Windows quiescence proof. Production backup, native Qdrant Server snapshots and go-live remain BLOCKED.

RAG-LAB.04 - restore saved-source directory reparse swap (2026-10-18)
Files: rag/runtime/offline_fixture_restore.py and tests/test_offline_lab04_restore_source_parent_swap.py.
RED: replacing saved snapshot source directory with a Windows directory symlink after copied store verification caused restore to publish without blocking, although all source content was identical.
GREEN: before restore publication, validate the original saved source, its parent, snapshot payload, metadata and all ancestor reparse boundaries again.
Regression: RAG-LAB.04 focused 54 PASS; backend 412 PASS (284 offline + 83 generation + 7 preflight + 38 incremental).
These are synthetic fixture defenses against observed races; they do not constitute atomic protection or global Windows process/mmap quiescence. Production backup and go-live remain BLOCKED.
