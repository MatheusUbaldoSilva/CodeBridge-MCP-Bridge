# RAG-LAB.01-F - CIM adverse conditions and failures (2026-10-17)

State: LAB COMPLETED. NOT production shutdown evidence.

## Changes
- offline_scoped_cim_observer.py now validates Windows CreationDate, stdout type/size, and clock ordering; clears partially validated PID lists on any parse/CIM failure.
- Incomplete identity rows keep the report BLOCKED and clear any previously accepted PID rows.
- Tests cover CIM timeout, permission denied, malformed JSON, oversized payload, clock reversal, invalid date, wrong executable type, and partial report errors.
- Production data, paths and full command lines are never returned by this observer.

## Evidence
- Focus: 17 scoped CIM observer tests and 2 CLI tests PASS.
- Full suite: 83 generation + 185 offline + 7 preflight + 38 incremental = 313 PASS, exit 0.
- All results retain copy_authorized=false, all_handles_closed=false, production_quiescence_proven=false.
- Limit: known PID scopes are not complete global Windows inventory, and mapping/handle release remains unproven.

Next: RAG-LAB.01-G   consolidated lab closeout with Qt smoke, Git diff review, commit/push and checkpoint.
