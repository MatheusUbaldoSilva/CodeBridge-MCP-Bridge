RAG-LAB.03-A — Static shutdown audit

Scope: source review only, not a proof of real process exit.

app_rewrite/ui.py closeEvent stops telemetry; run_ui returns when Qt event loop exits.
app_rewrite/main.py finally invokes runtime.stop() then releases SingleInstance.
app_rewrite/runtime.py stop ordering: secure_tunnel -> author_mcp (MCP and adapter) -> chatgpt_companion -> api -> engine -> terminals.close -> runtime file removal.
app_rewrite/secure_tunnel_manager.py stop terminates managed tunnel, closes log.
app_rewrite/author_mcp_manager.py stop terminates managed MCP and adapter, closes logs.
chatgpt_companion.stop and api_server.stop shutdown HTTP server and join thread(timeout=3).
executor.stop requests cancel_active and joins worker(timeout=5).

Risks: these joins do not prove child exit, orphan cleanup, Windows PID identity, mappings, WAL/SHM/journal release or global quiescence. MCP cannot independently certify its own exit.
RAG-LAB.03-B will add an EXTERNAL synthetic-only supervisor for its own child PIDs, never terminating the active CodeBridge installation.
copy_authorized=false
all_handles_closed=false
production_quiescence_proven=false
