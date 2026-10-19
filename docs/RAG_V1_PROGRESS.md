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

### V1.03-C - status de bloqueio explicitado para a publicacao
- rag/runtime/incremental_preflight.py inclui publication_gate {state:BLOCKED, reasons, safe_to_publish:false} na resposta do planejamento read-only
- Razoes objetivas: writer de geracoes nao conectado a producao, leitores MCP sem pin da geracao, verificacao completa Qdrant pendente, autorizacao de manutencao pendente
- Novas fontes sem aprovacao individual, worktree dirty e hashes desconhecidos acrescentam bloqueios adicionais quando presentes
- Prova no CodeBridge real via adaptador do repo: uma fonte NEW uma MODIFIED uma UNCHANGED e publication_gate BLOCKED com motivos listados
- Teste focado existente atualizado para evitar regressao do gate, 4 testes PASS
- A trilha de laboratorio generation_* permanece exclusivamente test-root; nao foi usada para modificar o indice ativo. Nao marcar V1.03-C concluida ate haver writer e leitores atomicos reais e autorizacao especifica

### V1.03-C - contrato de revisao de fontes no MCP
- Antes o MCP entregava classificacao delta sem identidade reproducivel do conjunto de arquivos selecionado
- Agora usa snapshot_preview + build_review_contract existentes em uma selecao de 1 a 20 fontes do root aprovado
- O recibo SHA-256 de 64 caracteres inclui caminhos + hashes atuais e retorna FINGERPRINTED_NOT_APPROVED; nunca concede autorizacao para publicacao
- Para inventario grande o retorno SOURCE_SELECTION_REQUIRED exige curadoria e selecao menor antes de revisar
- Prova real pelo adapter CodeBridge em repositorio aprovado: dois arquivos existentes, files_checked=2, review_sha256 valido, gate BLOCKED e execute=false
- Corrigimos testes legados do MCP que herdavam opt-in real via LOCALAPPDATA; cada subprocesso sintetico agora isola seu diretorio temporario sem alterar a politica de producao
- Regressoes focadas 4 preflight + 5 review contract + 3 preview confirmation + 3 MCP index + 9 index request = 24 PASS
- Ainda sem publicacao real: V1.03-C bloqueada aguardando integracao de geracao atomica, leitores travados e autorizacao especifica

### V1.03-C - fail closed real na solicitacao execute=true
- index_rag em codebridge com opt-in local e root aprovado bloqueia execute=true mesmo se um executor staging for registrado prematuramente
- Retorno de erro estruturado usa RagIndexExecutionUnavailableError / EXECUTOR_UNAVAILABLE explicando ausencia de registry aprovado, writer atomico e manutencao autorizada
- execute=false permanece disponivel e retorna preview digest de selecao e gate BLOCKED
- Prova real no CodeBridge pelo adapter do repositorio: PLAN permitiu consulta, EXECUTE recusado com EXECUTOR_UNAVAILABLE, nenhuma escrita no indice
- Testes legados do MCP com ambiente local isolado: 3 PASS; o bloqueio e aplicado ao contexto de instalacao opt-in, nao a executor customizado num teste isolado
- V1.03-C segue PARCIAL/BLOQUEADA: impedir publish nao constitui implementacao de publish

### V1.03-C — prova na instalacao e dependencias para proxima janela
- Commits recentes e188492 (motivos do gate), edaec06 (recibo de revisao) e d706404 (execute=true fail closed) verificados em origin
- Na instalacao Windows o adaptador atualizado retornou PLAN, FINGERPRINTED_NOT_APPROVED e gate BLOCKED
- Tentativa controlada execute=true no adaptador da instalacao retornou EXECUTOR_UNAVAILABLE antes de iniciar job; nenhum arquivo de indice modificado
- Os arquivos da instalacao correspondem aos fontes dos commits; processo MCP carregado precisa de reinicio externo seguro para disponibilizar publicamente os novos campos
- Etapa C ainda nao tem leitor de geracao ativado na producao, publicador atomico e prova Qdrant cross-store; nao reaproveitar modulo test-only como se fosse production-ready
- Proxima acao depois de reiniciar de forma manual e segura: codebridge_rag_index execute=false com 2 fontes aprovadas e verificar review_contract + publication_gate na ferramenta publica
- Depois implementar protocolo de geracao com snapshot consistente e pin de leitores antes de qualquer alteracao de indice real, com aprovacao especifica do operador
- Permanecem preservadas as duas excecoes antigas do working tree; nao alterar benchmarks/rag017_code_only_extended_smoke.json nem docs/RAG_017_J_VM_ROLLBACK_RUNBOOK_2026-10-10.md

### V1.03-C - previa legivel para operador usando codigo existente
- A API MCP de indexacao planejada agora tambem entrega preview_view reutilizando rag/runtime/incremental_preview_view.py existente, apenas com selecao de no maximo 20 fontes
- Retorna linhas com NOVO, ATUALIZAR, SEM ALTERACAO, resumo e publish_enabled=false. Para inventario grande exige selecao, sem dar falsa aprovacao
- Prova no repositório real via CodeBridge: 3 arquivos => rag_bridge.py ATUALIZAR, RAG_CONTRACT.md SEM ALTERACAO, RAG_V1_PROGRESS.md NOVO; executado=false
- O resumo explicita nenhum arquivo indexado, e o review_contract continua FINGERPRINTED_NOT_APPROVED
- Nenhum acesso fora do root ou mudanca do indice ativo; 3 testes focados existentes do modulo preview_view PASS

### V1.03-C — auditoria de consistencia vetorial READ ONLY no CodeBridge real
- Antes: o preflight comprovava 210 documentos 8761 chunks e manifesto mas nao comparava todos os IDs vetoriais do Qdrant Local sem abrir clientes de escrita
- Criado rag/runtime/live_integrity.py: abre exclusivamente SQLite mode=ro/query_only; confere integridade do indice SQLite e bancos Qdrant, pares doc/chunk/manifest hash e todos os IDs vetoriais deterministas
- Qdrant Local armazena IDs em base64/pickle. Interpretacao estatica de opcodes com allowlist via pickletools; NAO chama pickle.loads. Teste negativo adicionou ID malformado/dicionario proibido
- Verifica dimensoes e metrica em meta.json: Jina Text 1024 Cosine e Jina Code 1536 Cosine
- Prova real: SQLite principal 210 documentos 8761 chunks; Qdrant text=7627 e code=1134, 0 vetores ausentes ou extras, 0 mismatch no manifesto, PRAGMA integrity_check ok
- API MCP read-only codebridge_rag_integrity registrada no source instalado via RagIntegrityResult e bridge lazy; chamada direta do handler em Python CodeBridge embarcado retornou operation_ok=true / OBSERVED_CONSISTENT
- LIMITACAO EXPLICITA: snapshot_consistent=false e safe_to_publish=false. Uma leitura ao vivo nao demonstra quiescencia, pin de leitor, recuperacao nem publicacao atomica.
- Regressao focal: 9 testes do vector_ids e 4 preflight PASS, sem novo laboratorio e sem alterar banco ativo
- Proxima entrega: ativar novo tool MCP por reinicio gracioso externo e provar consulta publica; so depois manter plano de publicacao em geracao imutavel e manutencao aprovada

### V1.03-C — staging incremental REAL e manifesto compativel
- Para fontes que ja possuem versoes de modelo no manifesto ativo o indexador isolado agora cria rag-index-manifest.json junto com rag_index.sqlite3 e qdrant da nova geracao staging
- Novo modulo rag/runtime/staged_manifest.py compara SHA do arquivo real de novo apos embeddings; rejeita mudanca durante operacao e versoes ambiguas de modelo; nao grava em indice ativo
- Sem corpus ativo para o mesmo projeto o fluxo de staging anterior permanece compativel; plano vazio tambem segue suportado
- Testes legados: test_rag_017_g_staged_index 2 PASS e test_rag_017_g_staging_security 3 PASS
- PROVA NO SISTEMA REAL com CodeBridge: build_staged_index do arquivo ja commitado rag/runtime/live_integrity.py retornou STAGED_NOT_PUBLISHED, 1 documento, 5 chunks/code, 1 entrada de manifesto em 9.8 s
- Staging novo em %LOCALAPPDATA%/CodeBridge/rag/staging/build-ec8595a85ef44f59ba085a1b75b6e49a. Nao promover, nao apagar sem auditoria.
- Validador offline existente validate_incremental_bundle retornou VALIDATED_OFFLINE_NOT_PUBLISHED com 1 documento, 5 chunks, 5 vetores e 1 manifesto
- A prova e de staging real isolado NAO de update do indice ativo. Mesclagem/publicacao geracional e leitor protegido ainda pendentes. Nao houve novo laboratorio nem backup real

### V1.03-C — snapshot e merge do indice REAL (18/10, continuacao autorizada)
- O operador autorizou expressamente a manutencao controlada, mas o CodeBridge MCP nao foi interrompido e o indice ativo continua READY e sem substituicao.
- Criado rag/runtime/active_baseline.py: snapshot separado por SQLite backup de 3 bancos (principal, Qdrant text e code), copia imutavel de manifesto/meta, comparacao de tamanho/mtime e SHA de configs antes/depois e validacao integral do bundle fechado.
- BACKUP REAL: staging/baseline-4bd327885fe1472ca9b875433c3d8eb7; validacao VALIDATED_OFFLINE_NOT_PUBLISHED com 210 documentos, 8761 chunks, 8761 vetores e 210 manifestos. snapshot not_a_live_atomic_snapshot=true; activation_permitted=false.
- Criado rag/runtime/controlled_merge.py: exige root staging aprovado, recibo baseline, snapshot ativo sem drift e validacao individual dos dois bundles; mescla somente em pasta NOVA via 3 modulos incrementais existentes; confere schema, identidade e vetor sem alterar Qdrant ativo.
- Entrada staged original e real: staging/build-ec8595a85ef44f59ba085a1b75b6e49a, 1 documento/5 chunks/5 vetores Jina Code.
- Primeira mesclagem manual auditada: staging/merged-6b24a1cda086415798d35f9636b4454e; 211 documentos, 8766 chunks e vetores; recibo historico sem vinculo aos insumos, preservado apenas como evidencia.
- Mesclagem pelo codigo versionavel completo: staging/merged-3180ae4026e24134b03d916a21c30a92, recibo com baseline/candidate, 211 documentos, 8766 chunks/vetores e 211 manifestos. inspect_completed_merge revalidou read-only.
- PROVA de ponta a ponta: search_persistent_semantic diretamente no bundle novo, sem ponteiro de producao, Jina Code real retornou 8 resultados; rag/runtime/live_integrity.py apareceu entre os primeiros, modos VECTOR_CODE_COSINE e LEXICAL_FTS5_BM25.
- PORTAO PERMANECE: MERGED_VALIDATED_NOT_PUBLISHED e activation_permitted=false; nao existe ainda migracao supervisonada com reader pin do MCP, writer atomico e rollback comprovado na instalacao.
- Ambos os artefatos (backup original e mesclagem) foram preservados para rollback e nenhuma pasta ativa foi alterada. Nao criar novo laboratorio de testes.

### V1.03-D — duas geracoes reais preparadas sem ativacao
- Criado rag/runtime/generation_prepare.py: permite apenas bundles validados sob staging real, com recibos baseline/merge; copia cada bundle em um novo diretorio versionado, verifica SHA-256 de SQLite, manifesto e Qdrant e revalida o resultado.
- Geracao de recuperacao: %LOCALAPPDATA%/CodeBridge/rag/generations/v1_base_6142ab6e3b534f com 210 documentos, 8761 chunks, 8761 vetores e 210 manifestos.
- Geracao com delta: %LOCALAPPDATA%/CodeBridge/rag/generations/v1_delta_e4b1a435382f48 com 211 documentos, 8766 chunks, 8766 vetores e 211 manifestos.
- Ambas possuem generation-receipt.json com hashes, validacao e active_pointer_updated=false/activation_permitted=false.
- Auditoria posterior: active-generation.json AUSENTE; indice publico CodeBridge RAG continua READY com 210 documentos e 8761 chunks.
- O mecanismo test-only generation_process_lock recusa roots de producao. Nao reusar por simples troca de nome nem ativar ponteiro sem implementar e validar reader pin e writer lock reais.
- A copia de recuperacao nao pode ser retirada nem o indice legado sobrescrito durante a migracao. Ativacao V1.03-D permanece PENDENTE.

### V1.03-D — lock entre processos Windows e leitor fixado (preparado, sem migracao de handlers)
- Criado rag/runtime/production_generation_lock.py: LockFileEx Win32 no arquivo estavel production-generation.lock do root real CodeBridge/rag, reader shared vs writer exclusive; erros de ocupacao falham com ProductionGenerationBusy e o arquivo de lock jamais e excluido.
- Prova entre processos reais via CodeBridge Windows: reader shared ativo impede escritor exclusive em outro processo; liberando reader o writer adquire o lock.
- Criado rag/runtime/production_generation_read.py: adquire lock shared e resolve ponteiro ativo uma unica vez; sem ponteiro utiliza as rotas LEGACY SQLite/Qdrant/manifest e mantem o lock durante toda a operacao.
- Prova real: geracao legacy selecionada, SQLite e Qdrant presentes, writer exclusive recusado enquanto production_generation_read mantem o lock.
- ESTE CODIGO AINDA NAO ESTA CONECTADO AOS HANDLERS PUBLICOS MCP search/get_context e ao processo worker de embedding. Sem migracao completa dos leitores e writer de ativacao no mesmo lock, o ponteiro active-generation.json nao pode ser publicado.
- active-generation.json continua ausente; versoes preparadas v1_base_6142ab6e3b534f e v1_delta_e4b1a435382f48 permanecem NAO ATIVAS.
- Esta entrega nao reinicia MCP/GUI, nao substitui legado, nao apaga indices e nao indica GO-LIVE.

### V1.03-D - leitores MCP conectados ao production generation pin
- author_mcp/rag_bridge.py: para projeto codebridge, busca e get_context resolvem a mesma geracao durante lock shared production_generation_read(); legado sem pointer permanece acessivel.
- rag/runtime/v1_semantic_worker.py: o subprocesso Jina adquire seu proprio lock shared, seleciona SQLite/Qdrant/manifest pinados e pesquisa pelo _generation_paths; processo pai mantem lock durante o worker.
- rag/runtime/production_generation_read.py: leitura por pointer exige SQLite, Qdrant e manifesto; legado sem pointer permite indice SQLite simples compatibilidade lexical/documental. Indice inexistente conserva erros INDEX_UNAVAILABLE sem criar pastas artificiais.
- Prova executada no CodeBridge real: rota CODE com busca semantica 3 resultados, get_context conteudo de 1 chunk, writer exclusive adquiriu lock apenas APOS ambas as leituras terminarem.
- Regressao real existente 3 testes MCP search, 4 MCP get_context, 6 search_service e 5 context_service: total 18 PASS.
- IMPORTANTE: ainda nao ativar ponteiro: instalacao precisa receber novos arquivos e servico MCP publico necessita reinicializacao graciosa EXTERNA para carregar nova implementacao. Sem isso a sessao publica velha nao participa do lock.
- Writer atomico e rollback seguro permanecem dependencias do gate para corte; indice original 210 docs/8761 chunks, pointer ainda ausente.

### V1.03-D — verificacao de corte geracional e recuperacao, ainda bloqueada
- A versao instalada do rag/runtime/production_search.py possuia assinatura anterior sem _generation_paths; aplicado PATCH SELETIVO SOMENTE NA INSTALACAO para suportar caminhos fixados sem remover recursos experimentais historicos. A fonte versionada ja possuia esse suporte. Nao sobrescrevemos toda a instalacao.
- Prova do codigo instalado: busca Jina CODE 3 resultados, get_context 1 chunk, depois lock exclusive adquirido; 6.3s, nenhum SQLite/Qdrant ativo alterado.
- production_generation_read.py agora recusa novas leituras enquanto production-generation-transition.json existir (recuperacao obrigatoria), sob o mesmo lock de geracao. Nenhum journal foi criado nesta etapa.
- Novo rag/runtime/production_cutover_gate.py inspeciona somente leitura a integridade e os SHA-256 das duas geracoes versionadas e do indice legado e verifica que nao ha ponteiro/journal pendente.
- Prova com armazenamento real: v1_base_6142ab6e3b534f 210/8761, v1_delta_e4b1a435382f48 211/8766, SHA de ambos OK, indice legado 210/8761. Gate state=BLOCKED/safe_to_activate=false.
- Bloqueios concretos: leitores MCP publicos ainda nao atestados apos reinicializacao e writer de ponteiro atomico/rollback ainda NAO IMPLEMENTADO NEM VALIDADO. Nao criar active-generation.json, nao substituir indice legado.
- Proximo marco: introduzir publicador atomico COM journal, reinicio externo controlado do MCP, provar integridade e rollback antes de ativacao; duas geracoes originais devem permanecer imutaveis.
