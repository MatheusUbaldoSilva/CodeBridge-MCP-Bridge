# CodeBridge RAG V1 — progresso e patch notes

## 2026-10-18 — V1.00 / V1.01-A1 (parcial)

### Baseline MCP real
- CodeBridge 2.0.11-prealpha READY, indice codebridge READY com 210 documentos e 8761 chunks.
- HEAD inicial e7bd6ba, sincronizado com origin na branch rag-017-optimized-inference-after-candidate.
- Arquivos antigos preservados: benchmarks/rag017_code_only_extended_smoke.json (modificado) e docs/RAG_017_J_VM_ROLLBACK_RUNBOOK_2026-10-10.md (nao rastreado).
- Busca MCP existente reproduzida: TEXT e CODE solicitados; LEXICAL_ONLY efetivo, motivo SEMANTIC_EXECUTOR_UNAVAILABLE.
- Indice de 09/10 com source_revision null: atualidade e proveniencia ainda nao aprovadas.

### Alteracao logica V1.01-A1
- author_mcp/rag_bridge.py: opt-in local em %LOCALAPPDATA%/CodeBridge-MCP-Bridge/rag_v1_semantic.json, projeto codebridge somente.
- rag/runtime/v1_semantic_worker.py: usa Python configurado com qdrant-client e chama o retriever semantico real somente leitura.
- Motivacao: Python embarcado do MCP nao possui qdrant-client, embora o Python 3.13 do operador ja o possua. Nao instalar dependencia, nao modificar indice ativo, nao reiniciar MCP ativo.
- Resultado de compatibilidade: processo separado devolve SearchResult com metadados, usando os callbacks do bridge, falhas propagadas, timeout e fallback lexical explicito quando desabilitado.
- O arquivo de opt-in fica fora do Git por conter caminho local da instalacao.

### Evidencia
- Executor real via CodeBridge PowerShell + Python do operador: CODE efetivo com fallback null, encontrou author_mcp/mcp_server.py.
- Executor real via CodeBridge PowerShell + Python do operador: TEXT efetivo com fallback null, encontrou handoff Jina.
- Nenhum mock foi usado nessas duas consultas; nao equivalem ainda a validacao da ferramenta MCP publica em processo ativo.
- Git diff --check e compilacao Python validada; regressao focada de registro executada.
- Nao concluir V1.01 nem V1.02…07 sem teste da superficie publica instalada e provas restantes.

### Ativacao instalada e limites
- Copiar somente os dois arquivos novos/modificados para a arvore instalada apos commit.
- Processo MCP ativo ja importou rag_bridge anterior, portanto necessita reinicializacao autorizada pelo operador fora da propria sessao MCP para ativacao.
- Nunca encerrar GUI/adapter/MCP do proprio MCP e nunca promover, copiar, apagar ou reiniciar o indice RAG ativo.
- Proxima prova: codebridge_search_context pela ferramenta publica com effective_route=TEXT/CODE, arquivo atual, linhas e hashes conferidos.
- Gate GO-LIVE permanece BLOCKED, V1-LOCAL-CONTROLADA ainda PARCIAL.

### Deployment da V1.01-A1 na instalacao — evidencias posteriores
- Dois arquivos do commit f6b9cdb foram copiados para o CodeBridge Windows instalado; SHA-256 origem=destino para ambos.
- production_search.py da instalacao difere do repositorio por suporte de caminhos de geracao experimental. Diferenca auditada, arquivo instalado nao foi sobrescrito.
- Executando o novo bridge diretamente na arvore INSTALADA com Python 3.13 existente: requested_route CODE, effective_route CODE, fallback_reason null. Arquivo author_mcp/mcp_server.py retornado.
- Linhas 1249-1266 de author_mcp/mcp_server.py conferidas contra a instalacao e contra Git; mostram a definicao real da ferramenta codebridge_wait na linha 1261.
- Nova chamada a ferramenta publica codebridge_search_context com o MCP ja ativo permaneceu LEXICAL_ONLY / SEMANTIC_EXECUTOR_UNAVAILABLE, devido a importacao anterior do modulo. NAO reiniciar o MCP pelo proprio canal.
- V1.01 ainda PARCIAL: aguardar reinicializacao segura feita pelo operador e executar novamente TEXT e CODE pela ferramenta publica. Nao iniciar V1.02 antes dessa prova.
