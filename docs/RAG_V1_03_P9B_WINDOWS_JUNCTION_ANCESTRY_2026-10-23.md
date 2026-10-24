# P9-B — Windows junction / reparse ancestry refusal
State: tested in disposable lab; P9-B open.

Change: validate every lexical ancestor of TEMP-only scope and source, rejecting Windows junctions, symlinks and reparse points rather than relying only on Path.resolve and terminal-file symlinks.
Negative Windows tests create actual mklink /J directory junctions to a source and scope, requiring refusal before bundle creation. Sixteen focused bundle tests PASS; full P9B suite 554 tests PASS in 54.589s.
Files: installer/rag_p9b_frozen_disposable_bundle.py, tests/test_rag_p9b_frozen_disposable_bundle.py. No official NSIS or production registry modifications.
Remaining: trust root independent authentication, atomic one-journal NSIS transaction and supervisor auto-restart proof.