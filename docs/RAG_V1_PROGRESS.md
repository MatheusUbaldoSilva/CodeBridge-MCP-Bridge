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
- Prova TEXT na arvore instalada: requested_route TEXT, effective_route TEXT, fallback null, fontes docs/RAG_002_A_DOCUMENT_SOURCES.md e docs/HANDOFF_RAG_017_024_KNOWLEDGE_MANAGEMENT_UI_2026-10-08.md, sem mock.

### 2026-10-18 — continuacao V1.01-C/D (ainda PARCIAL ate reinicio externo seguro)
- Na nova sessao CodeBridge `NORMAL`, o MCP publico ainda trouxe CODE/TEXT solicitados com LEXICAL_ONLY/SEMANTIC_EXECUTOR_UNAVAILABLE: processos Python MCP atuais iniciados antes da copia da atualizacao instalada. Nao os parar a partir do proprio MCP.
- V1.01-D identificou defeito real de atualidade: a busca MCP publica devolveu `stale=false` em author_mcp/mcp_server.py mesmo com SHA indexado divergente; `codebridge_get_context(project_root=repo)` bloqueou corretamente com STALE_RESULT/SHA_MISMATCH.
- Patch em author_mcp/rag_bridge.py: em consultas do projeto codebridge com opt-in habilitado e repository_root explicitamente aprovado, cada resultado e comparado com arquivo real por `evaluate_source_staleness`. Retorna `source_verification={status,reason,current_sha256}` e `stale=true` quando STALE/UNKNOWN/UNVERIFIED. Root fora do repositorio/Git invalido rejeitado. Nao altera indice.
- Patch em rag/runtime/v1_semantic_worker.py: JSON stdout com `ensure_ascii=True` para transporte ASCII seguro no Python Windows cp1252, preservando Unicode apos JSON decode; antes uma consulta real falhou com UnicodeEncodeError ao encontrar simbolo de check.
- Opt-in local passou a declarar `repository_root=C:\Users\Matheus\CodeBridge-MCP-Bridge`, sem armazenar config pessoal no Git.
- PROVA REAL CodeBridge pelo bridge em Python do repositorio: CODE effective_route=CODE, 10 resultados, autor_mcp/mcp_server.py agora corretamente STALE, demais arquivos do exemplo FRESH. TEXT effective_route=TEXT, documentos de handoff FRESH. Negativos no repositorio real: hash divergente STALE e path escapando escopo UNVERIFIED/stale=true.
- Regressao focada existente: 6 search service + 3 registration + 4 production search + 7 source staleness + 3 MCP search = **23 PASS**, executados no CodeBridge real.
- PENDENCIA: processo MCP publico ainda carregado com modulo anterior; V1.01 nao fechada ate reinicio manual do app e prova TEXT/CODE pelas ferramentas publicas. V1.02-V1.07 bloqueadas pela sequencia do handoff. Indice ativo nao copiado, atualizado nem alterado; sem novo laboratorio.

### V1.01 — pesquisa MCP real e CPU fallback (2026-10-18, nova sessao)
- Reinicio manual normal do operador comprovado: processos MCP novos, CodeBridge 2.0.11-prealpha READY e terminais online.
- MCP publico codebridge_search_context CODE: requested=CODE, effective=CODE, fallback=null, modos VECTOR_CODE_COSINE + LEXICAL_FTS5_BM25, fonte atual verificada e STALE detectado para mcp_server.py.
- MCP publico TEXT: requested=TEXT, effective=TEXT, fallback=null, VECTOR_TEXT_COSINE + lexical, documento docs/RAG_CONTRACT.md FRESH; codebridge_get_context pelo project_root real validou linhas 35-45 e integridade.
- MCP publico HYBRID: requested=HYBRID, effective=HYBRID, lexical + vetor texto + vetor codigo coexistem, com hashes FRESH verificados.
- V1.01-E fallback CPU: reutilizado TextModelFallbackManager.auto em rag/runtime/production_search.py para os dois modelos, sem novo servidor/laboratorio. Prova real CPU sem GPU no Windows: Text Jina DIM=1024 tempo 10.57s; Code Jina DIM=1536 tempo 5.25s. Implementacao normal _embed_text e _embed_code comprovada em execucoes reais DIM 1024/1536. Quatro suites focadas existentes 1+4+11+14 = 30 PASS.
- Reinicio e retorno do MCP provados. Sem copia/backup/rebuild do indice. V1.01-BUSCA SEMANTICA MCP comprovada; validação de fallback automatico por falha real de GPU na ferramenta MCP em producao NAO executada (somente rota CPU real isolada e backend normal). Gate oficial GO-LIVE permanece BLOCKED.

### V1.02 — cinco casos reais de pesquisa
- (1) codebridge_wait: autor_mcp/runtime_client.py e test_wait_tool.py encontrados, mas mcp_server.py STALE na indexacao antiga.
- (2) parada graciosa: documentos encontrados, porem top-1 foi chunking de logs pouco relevante; melhorar ranking com medicao futura.
- (3) registro semantico: author_mcp/rag_bridge.py encontrado corretamente mas STALE por commit novo.
- (4) decisao de nao indexar logs: handoffs e politicas retornados, relevancia semantica top-1 irregular.
- (5) indexacao incremental: rag/index/incremental.py em top-1 e outros candidatos.
- Nenhuma busca falhou e todas indicaram rota real; ainda ha trabalho de ranking e indice antigo para V1.02 concluir.

### V1.02 — prioridade para fonte verificada, sem apagar evidencias
- author_mcp/rag_bridge.py: depois da recuperacao e da verificacao de SHA, resultados FRESH sobem antes de STALE/UNVERIFIED mantendo esses registros historicos presentes com rank reenumerado e scores do recuperador originais preservados.
- Prova no CodeBridge real com repositório local: CODE registradores semânticos -> posicoes 1-4 FRESH e 5-8 STALE, nenhum resultado desapareceu.
- Cinco pesquisas de avaliacao registradas acima; seguir depois com criterio de relevancia especifica e reindexacao para corrigir fontes antigas.
- A nova ordenacao ainda necessita reinicio gracioso do processo MCP publico para ser observada na ferramenta publica; nao interromper por dentro do proprio MCP.

### V1.03-A/B - inventario e delta real read-only
- codebridge_rag_index execute=false aceitou docs/RAG_V1_PROGRESS.md no root aprovado; scope TEXT, 1 candidato, 0 deny/unsupported/sensitive; nenhuma execucao pesada.
- assess_incremental_plan no SQLite ativo em modo somente leitura: docs/RAG_CONTRACT.md UNCHANGED, author_mcp/rag_bridge.py MODIFIED, docs/RAG_V1_PROGRESS.md NEW; new=1 modified=1 unchanged=1 unknown=0.
- A API existente retorna safe_to_publish=false e informa explicitamente que a publicacao incremental ainda nao foi implementada e validada.
- Proxima letra V1.03-C requer desenho/validacao de publicacao atomica e autorizacao especifica antes de alterar indice ativo. Nao houve copia, backup, reindexacao nem escrita em SQLite/Qdrant reais.
- Teste de reclassificacao foi executado por CodeBridge MCP no projeto real; nenhuma nova trilha de laboratorio criada.

### V1.03-C - preview MCP incremental real somente leitura
- Antes: index_rag execute=false so listava candidatos sem delta nem Git
- Agora: rag_bridge usa assess_incremental_plan em codebridge com opt-in e root aprovado, sem escrever no indice
- O preflight classifica novo modificado e inalterado; remocao e renomeacao potencial apenas em inventario integral BOTH
- Proveniencia: HEAD do Git e arquivos modificados ou untracked do escopo diferem do hash indexado
- Prova real no CodeBridge: 3 fontes consultadas com Git AVAILABLE e alteracoes locais corretamente vistas, execute=false safe_to_publish=false
- Inventario real completo: 864 candidatos elegiveis, 654 fora do indice, 3 modificados, 207 inalterados, zero remocoes, 4.24 segundos
- Candidatos nao significam fontes aprovadas e nao iniciam indexacao
- Regressao focada adicionada ao teste existente: rename somente no inventario integral e sem alterar SQLite
- Bloqueio de publicacao: incremental_offline_publish e generation_* sao exclusivos de tests roots; safe_to_publish=false
- Sem permissao especifica e locking independente nao copiar parar GUI alterar indice ativo nem gerar backup real
- Defesa adicional: o planejamento codebridge recusa project_root fora do root previamente aprovado ANTES de listar ou ler arquivos; comprovado por tentativa real bloqueada com PermissionError e plano permitido no root correto.

### V1.03-C - validacao instalada e integridade (continuacao)
- Commit da implementacao 1fb241a97562f69ac2f73706948301e3ceb61452 sincronizado com origin
- Copia controlada para instalacao Windows apenas author_mcp/rag_bridge.py e rag/runtime/incremental_preflight.py; hashes fonte/destino identicos e compilacao no Python embutido OK
- Prova na arvore instalada: index_rag(scope=BOTH, 3 arquivos, execute=false) retornou NEW progress, MODIFIED rag_bridge, UNCHANGED contrato, git_status AVAILABLE, HEAD=1fb241a, tempo 0.18 s, safe_to_publish=false
- Chamada pela ferramenta MCP publica nesta sessao ainda sem incremental_preview por import cache do processo; aguardar reinicio manual seguro para validar superficie publica; nao reiniciar processo MCP por dentro dele
- SQLite ativo verificado somente leitura: PRAGMA integrity_check=ok, 210 docs, 8761 chunks, 0 orfaos; manifest existe com entries e schema_version
- Revisao de gate: sem vetor Qdrant consistente sob sessao fechada, locking e publicacao atomica comprovados nao ha aprovacao para trocar geracao ativa; V1.03-C, D e E permanecem parciais/bloqueadas
- Nao foi executada indexacao, backup real, copia do indice, exclusao, parada de GUI ou alteracao de DB
