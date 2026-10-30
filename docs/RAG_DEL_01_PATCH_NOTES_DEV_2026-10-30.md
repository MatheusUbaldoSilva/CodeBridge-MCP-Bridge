RAG-DEL-01 — Patch notes de desenvolvimento DEV 2026-10-30

Commits de desenvolvimento: 8186a27, 7fe7870, 5afc57d, 2b60830, 254700a, 0d88747, b97b3d9, 355f563, 69484b7.

Adicionado suporte de leitura à família RAG_DEL_01 no resolver privado, vinculado a recibo SHA256, snapshot, banco SQLite, manifesto, Qdrant fechado e progresso. Incluído montador de recibo exclusivamente para laboratório temporário e verificador da geração antes de troca/rollback em catálogo temporário. Auditoria estrutural independente SQLite/FTS/manifesto integrada ao validador de candidato. Caminhos Windows com barra invertida simples recusados na prévia de exclusão. Testados estágio interrompido e rollback de catálogo de laboratório sem mocks de validação.

Validação final: 371 testes RAG-AUTO/RAG-DEL/Qt executados, 364 PASS, 7 SKIP, 0 FAIL. Cinco testes MCP previamente aprovados; repetir checagem após este arquivo.

Sem exclusão real, sem troca de catálogo de produção, sem push e sem alterações Stable/público/newworldpvp. A exclusão operacional permanece bloqueada até recibos completos, recuperação e homologação em cenários reais autorizados.
