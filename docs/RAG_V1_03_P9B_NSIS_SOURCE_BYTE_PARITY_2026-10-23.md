# P9-B ? byte-level evidence for isolated NSIS candidate

Date: 2026-10-23
Status: READ-ONLY CANDIDATE VALIDATION / NO CUTOVER

The existing staged candidate P9B_SOURCE_ONLY_b3e5e5e42e5f_TREE/
installer/dist/CodeBridge-Setup.exe remains SHA256
B9A6409E809D495D76AB8BFFEDA1BB94A41563539002090F6AFAC20C89FB0C2B.
Using 7-Zip e -so (no execution of Setup), individual NSIS entries
were compared byte-for-byte to the exact isolated Git archive source tree:

- app_rewrite/main.py ? PASS
- author_mcp/mcp_server.py ? PASS
- rag/runtime/production_index.py ? PASS
- version.json ? PASS
- installer/p9b_update_process_guard.py ? PASS

The repository-only installer/rag_p9b_rollback_journal.py was not
present as a payload entry. The NSIS file list explicitly enumerates
the installer support modules, excluding this recovery journal module.
Its known imports were found in other installer/rag_p9b_* laboratory
and recovery modules, not in the installed app_rewrite/author_mcp/rag
modules in the searched source scope. This indicates an external
recovery dependency; packaging that module into the live application
was NOT inferred or performed. The external supervisor must carry
its own independently attested source and dependencies.

No NSIS execution, installed file replacement, actual registry
mutation or MCP shutdown was performed. These positive comparisons
are not evidence of real rollback or post-update CBMCP/1 continuity.
P9-B remains OPEN.
