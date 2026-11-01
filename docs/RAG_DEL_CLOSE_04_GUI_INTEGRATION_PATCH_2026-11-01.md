# PATCH NOTES — RAG-DEL integrated GUI locked delete test

Date: 2026-11-01
Branch: dev-local

## Added test coverage
- tests/test_rag_del_close_04_ragpanel_integration_dev.py
  - Constructs the actual RagPanel in Qt offscreen mode.
  - Checks locked "Excluir conhecimentos" exists inside Meus arquivos.
  - Rejects project-switch unlocking, including the protected public project.
  - Ignores forged preview metadata claiming deletion is operational.

## Verification
- 3 GUI integration tests passed.
- RAG-DEL regression: 782 executed, 776 passed, 6 skipped, 0 failed.
- RAG-AUTO non-MCP: 241 executed, 236 passed, 5 skipped, 0 failed.
- Three MCP-specific RAG-AUTO modules excluded only because 'mcp' is not
  present in the tested DEV interpreter; not treated as passes.
- Source-tree testing only; no installed GUI, Stable, live index, cutover
  or credentials modified.

## Acceptance
CLOSE-03 still blocked, CLOSE-04 incomplete, no operational deletion.
Functional gate score stays 40/100.
