# RAG-DEL-01.04 DQ-E-D-3C-G-17 — Manual soak direct-entrypoint fix

The G-13 manual 1..500-iteration scratch-only benchmark originally worked when imported as a module but failed when invoked directly with "python benchmarks/rag_del_mac_pipe_soak_dev.py" because Python uses the benchmarks directory as sys.path[0]. This patch adds a narrowly scoped repo-root import path ONLY for direct script invocation. The module-mode import path and MAC protocol remain unchanged.

Four focused tests PASS, including direct invocation from the repository root. The benchmark remains strictly scratch-only and never authorizes real RAG deletion, indexing or generation publishing. No Stable, queue, installed GUI/MCP or GitHub changes.
