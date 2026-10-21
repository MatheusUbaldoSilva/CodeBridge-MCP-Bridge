# RAG V1 P4 - Pre-cutover 2026-10-21

Operador autorizou manutencao administrativa e Remote Desktop.

Nova geracao: v1_delta_3ab9c095605b4a
Baseline: v1_base_6142ab6e3b534f
Candidata: 211 documentos, 8774 chunks e vetores.
Publico: legacy 210 documentos e 8761 chunks.
Fonte nova: rag/runtime/incremental_scheduler_gate.py
Fontes reindexadas: author_mcp/mcp_server.py, author_mcp/rag_bridge.py, rag/runtime/production_index.py, rag/runtime/production_search.py, rag/runtime/status.py.
SOURCE_SNAPSHOT_CURRENT com 211 fontes, zero alteradas ou ausentes.

Public MCP readiness: PUBLIC_HYBRID_CONCURRENCY_PASS, PID 9300, tres consultas HYBRID aprovadas, reader pin ativo, serializacao de worker ativa, integridade OBSERVED_CONSISTENT.

Cutover ainda NAO EXECUTADO. O ensaio antigo author_mcp/v1_supervised_live_trial.py aponta para outra geracao de 8778 chunks e nao deve ser usado. Necessario adaptar ensaio, gerar atestados novos e provar rollback supervisionado. Nao substituir apontador publico sem validacao.

GO_LIVE_BLOCKED. Git e fontes atuais continuam autoridade tecnica.
