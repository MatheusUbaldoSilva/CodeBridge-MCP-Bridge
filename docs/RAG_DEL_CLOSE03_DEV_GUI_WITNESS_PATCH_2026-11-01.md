# CLOSE-03 — Installed DEV GUI in-process witness (read-only)

Date: 2026-11-01. This patch does not activate deletion.

Files:
- app_rewrite/ui.py: starts a one-shot independent GUI witness after Qt window.show()
- rag/runtime/knowledge_deletion_gui_witness_dev.py: responds once with a
  challenge echo, current process PID/birth and SHA256 of in-memory Python
  class method code objects in rag_panel and rag_deletion_review_panel.
- rag/runtime/knowledge_deletion_gui_witness_verify_dev.py: independent verifier
  pins expected kernel GUI process PID, process creation time and actual kernel
  Named Pipe *server* PID, checks fresh 256-bit challenge echo and parses
  in-process loaded code receipts; no deletion capability.
- tests/test_rag_del_close_03_gui_witness_dev.py: real distinct-process offscreen
  GUI import and one-shot IPC witness test; rejected invalid process birth.

Assurance boundary: kernel-pinned challenge reply proves observed GUI process
responded with its in-memory code hashes at that moment. This is a DEV
diagnostic, not a formal secure code-signing attestation or proof of active
GUI request authorization. Peer effective IPC token/ACL must be checked on
the installed witness transport separately. Existing windows terminal-control
pipe is not reused. The witness cannot read or write any RAG queue/catalog,
cannot invoke deletion, and always returns activation_authorized=False.

Regression: 796 RAG-DEL tests, 790 PASS, 6 SKIP, 0 FAIL; diagnostic tests 2 PASS.
No pre-existing dirty files were staged, no Stable/GitHub modifications.
A separately operator-controlled rollback/canary resolution is still needed
before G32 can ever be considered cleared.
