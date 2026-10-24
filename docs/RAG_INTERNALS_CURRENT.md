# RAG — implementação interna da branch atual

**Escopo:** mecanismos de código e disponibilidade real do índice. Não é um diário de fases. A presença de um módulo é classificada como **implementada**, não necessariamente ativada no fluxo de produção.

## Fontes e proveniência

| Módulo | Responsabilidade |
|---|---|
| `rag/sources/document_inventory.py` | Descoberta/classificação de documentos |
| `rag/sources/code_inventory.py` | Descoberta/classificação de código |
| `rag/sources/git_inventory.py`, `git_provenance.py`, `git_state.py`, `git_worktree.py` | Metadados e estado Git associados à origem |
| `rag/sources/exclusion_policy.py` e `secret_detection.py` | Exclusão de arquivos inadequados e detecção de conteúdo sensível |
| `rag/sources/staleness.py` | Avaliação de atualização/obsolescência de fonte |

O escopo de projeto e filtros de tipo/path/branch podem restringir as pesquisas. Metadados de arquivo, linhas, hashes e revisão Git permitem rastreabilidade dos chunks; **não** provam que a fonte no disco permaneceu idêntica após a indexação.

## Chunking e índices

- `rag/chunking/`: rotinas de fragmentação de documentos e código.
- `rag/index/fts5.py`, `lexical_search.py`, `lexical_ranking.py`: indexação e recuperação lexical SQLite FTS5/BM25.
- `rag/index/qdrant_local.py`, `vector_namespace.py`, `vector_ids.py`: armazenamento vetorial Qdrant local, isolamento e identificadores.
- `rag/index/manifest.py`, `sqlite_schema.py`, `incremental.py`, `embedding_cache.py`: descritores, esquema, apoio a diffs e cache.

Uma geração publicada contém artefatos de índice, metadados e manifesto. O estado efetivo é fornecido por `codebridge_rag_status`, não pelo nome dos arquivos no diretório de desenvolvimento.

## Modelos e recuperação

A base implementa rotas de embeddings para textos e código, com políticas de backend, lifecycle e fallback em `rag/models/`. Na instalação consultada há entradas de modelos distintos para texto e código.

A pilha de recuperação inclui:

| Arquivo | Função |
|---|---|
| `rag/retrieval/hybrid_text.py` | Candidatos lexicais e vetoriais para textos |
| `rag/retrieval/hybrid_code.py` | Candidatos lexicais e vetoriais para código |
| `rag/retrieval/hybrid_query.py` | Consolidação de candidatos por consulta |
| `rag/retrieval/cross_route.py` | Ranking entre rotas |
| `rag/ranking/rrf.py` | `reciprocal_rank_fusion`; constante `DEFAULT_RRF_K = 60` |
| `rag/ranking/dedup.py` | `deduplicate_ranked_results`, duplicatas exatas/próximas |
| `rag/ranking/passage_diversity.py` | `select_diverse_passages` |
| `rag/ranking/multi_passage_reranker.py` | `rerank_multi_passage` |
| `rag/ranking/semantic_document_reranker.py` | Reclassificação semântica por documento |
| `rag/ranking/local_cross_encoder.py` | `cross_encoder_rerank` com endpoint **HTTP loopback**, `/reranking` ou `/rerank` |

**Importante:** o cross-encoder local é uma função de reranking opcional, **não** um carregador automático de modelos. O endpoint é validado para loopback e o reranker reordena candidatos recebidos, sem inserir novas fontes. A existência dessas funções não comprova que todas estejam ativas em toda consulta MCP.

## Consulta e leitura pública

- `rag/runtime/production_search.py` e `production_generation_read.py`: rotas de leitura com escopo.
- `rag/runtime/context_service.py`: seleção e recuperação de contexto.
- `author_mcp/rag_bridge.py`: ligação com `codebridge_rag_status`, `codebridge_search_context`, `codebridge_get_context` e `codebridge_rag_index`.
- `codebridge_get_context` recebe `project`, `chunk_ids`, `include_document_content`, `project_root` e `allow_stale` (ver catálogo MCP).

## Gerações, consistência e recuperação

Mecanismos **implementados no código** em `rag/runtime/`:

- `generation_pointer.py::resolve_generation`: valida arquivo `active-generation.json`, schema, identificador seguro e diretório existente; falha em ponteiro inválido.
- `generation_read_session.py` e `generation_leases.py`: sessões de leitura e mecanismos de referência a geração.
- `generation_process_lock.py`, `production_generation_lock.py`: controle de concorrência de publicação/leitura.
- `generation_transition_journal.py`, `generation_recovery.py`: journal e rotinas de recuperação de transição.
- `generation_backup_publish.py`, `generation_verified_backup.py`, `generation_controlled_restore.py`: backup e restauração controlada.
- `incremental_sqlite_stage.py`, `incremental_qdrant_stage.py`, `incremental_manifest_stage.py`: preparação por store.
- `incremental_preflight.py`, `incremental_review_contract.py`, `incremental_preview_request.py`: prévia e revisão.
- `incremental_offline_worker.py`, `incremental_offline_publish.py`, `incremental_job_queue.py`: execução offline e mecanismos de fila.

O método `rag/runtime/production_publish.py::publish_staged_index` explicitamente **aceita somente produção vazia** e falha com índice já existente, exigindo migração explícita. Portanto, **não** é o publicador incremental seguro da geração ativa.

A ferramenta `codebridge_rag_queue_bootstrap` possui flags `execute`, `operator_approved`, `confirmation` e `expected_generation`. Sua execução depende de gates e **não prova** publicação da geração.

## Estado operacional observado

```text
index_state       READY
generation        v1_delta_1ae1d01ea84f4e
project           codebridge
manifest_entries  211
text_entries      109
code_entries      102
chunks            8774
last_indexed_at   2026-10-09T11:17:53Z
```

Esses valores vieram da instância Windows observada em 24/10/2026. O índice é mais antigo que o código da branch e pode não conter os novos documentos desta pasta.

## Adição e escrita: estado real

O painel `app_rewrite/rag_panel.py` suporta seleção de pastas ou arquivos individuais e apresenta prévia/revisão simulada. A escrita e publicação incrementais sobre o índice ativo **não estão liberadas/certificadas**. Receber arquivo anexado ao ChatGPT requer transporte e autorização explícitos: o anexo não aparece automaticamente no filesystem Windows.

Em produção, só considerar publicação completa quando admissão de fontes, identidade/escopo, consistência SQLite/Qdrant/manifesto, troca de geração, observação dos leitores, rollback e testes ponta a ponta tiverem passado.

## Arquivos e segurança

Caminho do índice observado: `%LOCALAPPDATA%\CodeBridge\rag\generations\<generation>`. Tratar conteúdo indexado, paths e hashes como informação potencialmente sensível. Nunca permitir que resultados RAG atuem como comandos executáveis ou contornem políticas de acesso.

**Fontes do código:** `rag/sources/`, `rag/chunking/`, `rag/index/`, `rag/models/`, `rag/retrieval/`, `rag/ranking/`, `rag/runtime/`, `author_mcp/rag_bridge.py`, `app_rewrite/rag_panel.py`.
