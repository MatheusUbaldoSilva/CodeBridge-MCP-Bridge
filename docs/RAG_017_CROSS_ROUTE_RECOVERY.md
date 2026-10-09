# RAG-017 — Recuperação vetorial cruzada CODE sobre perguntas TEXT

## Motivo da correção
As 100 queries congeladas do RAG-014 foram reavaliadas no índice persistente publicado, com fontes originais e thresholds inalterados. O diagnóstico `benchmarks/rag017_recovery_failure_cases.json` encontrou quatro consultas sem fonte esperada nos candidatos da rota original: `rag014-053`, `rag014-078`, `rag014-080`, `rag014-098`. Todas estavam na rota TEXT e esperavam fontes `.py`. Os arquivos estavam indexados, mas a recuperação TEXT priorizava documentação.

## Estratégia geral (opt-in)
`rag/retrieval/cross_route.py` oferece `cross_route_document_rank`. Dado o mesmo `SearchQuery`, as listas candidatas já filtradas e um embedding CODE NL2CODE, executa `search_code_vector` com os filtros de projeto/source_type/branch/path já implementados e reclassifica no nível de documento com `rerank_documents(rrf_k=10)`. A função rejeita mistura de projetos.

A função exige explicitamente embedding CODE, sem baixar modelo, iniciar servidor ou ativar busca global. A aplicação instalada e o executor `production_search` não foram alterados.

## Resultados reproduzidos (100 queries conhecidas)
Relatório `benchmarks/rag017_cross_route_exploration.json`. Script `benchmarks/diagnose_rag017_cross_route.py`.

| Métrica | Documento anterior | CODE complementar | Threshold |
|---|---:|---:|---:|
| Recall@5 | 0,82 | **0,89** | 0,80 |
| Recall@10 | 0,91 | **0,95** | 0,90 |
| MRR | 0,596595 | **0,704806** | 0,60 |

Estes valores ultrapassam os limiares **no dataset exploratório conhecido**. Isso NÃO aprova o gate de produção: o mesmo corpus e as mesmas 100 perguntas já orientaram numerosas explorações, com risco de overfitting. Não há holdout independente.

A evidência é causalmente consistente com a lacuna da rota TEXT: `rag014-053` passou a trazer `rag/runtime/context_service.py` em 2º, `rag014-078` passou a trazer `rag/sources/git_provenance.py` em 2º e `rag014-098` passou a trazer `rag/sources/git_state.py` em 2º. A quarta query permanece sem fonte esperada no top10 expandido.

## Trade-offs antes de produção
- Embedding CODE adicional pode demandar troca de modelo na RTX 3050 6GB, mesmo quando a consulta é TEXT; precisa medir **cold, warm p95 fim a fim, RAM, VRAM e transição Jina Text/Code**.
- A política de busca para todos os queries do experimento não necessariamente é ótima para datasets não vistos. Criar validação independente antes de introduzir heurísticas ou seletor condicional.
- Verificar query source_type, branch, path e namespace também na integração no executor instalado; a função auxiliar apenas protege candidatas e delega filtragem de vetores.
- Reexecutar leitura do estado READY e avaliar índice atualizado após commits, pois o snapshot publicado pode ficar obsoleto em relação à versão corrente do repositório.
- Só declarar PASS quando a avaliação não enviesada e os limites de latência/recursos satisfizerem conjuntamente os critérios congelados.

**Estado: READY técnico do índice, gate de produção BLOCKED. RAG-017-J não iniciado.**
