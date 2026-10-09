# RAG-017-G — Production Executors — Fechamento técnico

## Objetivo e resultado
Implementar e disponibilizar para registro explícito os executores reais de indexação e busca semântica do CodeBridge RAG. **A ativação automática do índice de produção não faz parte desta fase.** Os critérios de qualidade RAG-017-I continuam BLOCKED: o RAG-017-F mediu Recall@5 0,77 (meta 0,80), Recall@10 0,83 (meta 0,90), MRR 0,53182 (meta 0,60).

## Executor de indexação
`rag/runtime/production_index.py:build_staged_index` recebe o `RagIndexPlan` produzido após a validação de escopo do projeto. Revalida caminho relativo, existência da fonte, denylist e conteúdo sensível imediatamente antes da leitura. Cria SQLite/FTS5 e Qdrant Local em um diretório **isolado de staging**, indexa chunks com IDs determinísticos e embeddings Jina Text e Jina Code, carrega um modelo por vez e fecha os recursos. Registra branch e HEAD quando existe Git. Em caso de falha, fecha o SQLite, limpa o staging criado e propaga a exceção.

O retorno `STAGED_NOT_PUBLISHED` inclui caminho de staging, projeto, documentos e contagens de chunks. O executor **não promove** o estágio, **não altera** o índice ativo, **não publica manifest** e **não declara READY**. Publicação durável, rollback, múltiplos projetos e recuperação após reinício serão tratados no RAG-017-H.

## Executor de busca
`rag/runtime/production_search.py:search_persistent_semantic` aceita `SearchQuery` e `QueryRoute`, e lê apenas um índice previamente marcado READY com SQLite e Qdrant presentes. Carrega modelo TEXT e/ou CODE sob lock compartilhado, produz embeddings de consulta, aplica a busca lexical FTS5 e busca vetorial Qdrant com filtros de namespace/projeto, source type, branch e path, usa RRF (k=60) e dedup, retorna `SearchResult`. Não cria índice nem grava arquivos de projeto. Quando o estado não é READY, falha fechado antes de carregar modelo.

## Registro MCP opt-in
`author_mcp/rag_bridge.py:configure_production_rag_executors` chama os registradores já existentes sob controle explícito:
- `staged_index=True` registra `build_staged_index`.
- `semantic_search=True` registra `search_persistent_semantic`.
- O padrão é **não ativar** nenhum registro. O MCP continua preservando `execute=False`, erro explícito de executor indisponível e fallback lexical quando não registrado.

O teste do registro não modifica os processos instalados em execução. H deverá fazer a ativação controlada somente após provar publicação, consistência, restart e recovery. Os adaptadores escritos aqui integram a árvore-fonte; deployment ao instalador é etapa separada.

## Provas reais
- `benchmarks/run_rag017g_staged_smoke.py`: um documento, um chunk/vetor e limpeza de staging.
- `benchmarks/run_rag017g_staged_search_smoke.py`: staging Jina real seguido de busca semântica real com índice temporário sinalizado READY apenas dentro de mock de teste, fonte correta recuperada.
- `benchmarks/run_rag017g_dual_model_smoke.py`: texto + código, ambas coleções vetoriais com contagens coerentes, sem publicação.

## Testes de segurança
- `tests/test_rag_017_g_production_search.py`: rota e estados inválidos bloqueados.
- `tests/test_rag_017_g_pipeline.py`: carregamento apenas do modelo exigido e encerramento do Qdrant.
- `tests/test_rag_017_g_registration.py`: opt-in explícito, preservação do padrão anterior.
- `tests/test_rag_017_g_staged_index.py`: isolamento de staging e validação de plano.
- `tests/test_rag_017_g_staging_security.py`: path sensível negado, limpeza em falha, gravação de branch e commit Git.
- Suite de regressão RAG e integração real Streamable HTTP MCP executadas antes do fechamento Git.

## Limitações e próximos gates
1. RAG-017-H precisa promover o índice de staging de maneira consistente para SQLite, Qdrant e manifest, verificar retomada e reconstrução após restart e habilitar os executores no runtime instalado.
2. O estado de produção continua não READY; G não significa salvamento automático de contexto.
3. RAG-017-I deve aprovar métricas de recuperação e desempenho com thresholds congelados antes de liberar o go-live.
4. O uso atual de GPU/CUDA0 depende do runtime local Jina e llama-server; fallback e configuração em outras máquinas devem ser verificados antes de distribuição geral.

## Política de encerramento
Revisão de diff, suite de regressão, commit, push e auditoria pós-commit obrigatórios. Nenhum índice ativo foi criado ou promovido neste marco.
