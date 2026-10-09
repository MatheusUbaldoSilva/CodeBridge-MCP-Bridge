# RAG-017-D — Diagnostico da recuperacao vetorial e chunking

## Escopo
Investigar fontes esperadas fora dos top-k, separando TEXT e CODE; rever os mecanismos de recuperacao e chunking quando houver evidencias suficientes. Mantidos os contratos de seguranca, os modelos locais e os thresholds.

## Evidencia examinada
- `benchmarks/rag017_failure_matrix.json` e `benchmarks/rag017_component_trace.json` da fase A;
- implementacao `rag/retrieval/hybrid_text.py`, `hybrid_code.py` e `hybrid_query.py`;
- `benchmarks/audit_rag017d_vectors.py` e `rag017d_vector_diagnostic.json` (100 consultas com rotas, fontes esperadas, candidatos vetoriais e contagens de diversidade).
- O replay de A usa corpus temporario; resultados nao representam indice de producao.

## Achados observacionais
- Fonte esperada dentro do top 10 vetorial: **48 / 100**.
- Fonte ausente do top 10 vetorial: **52 / 100**.
- TEXT: 22 hits e 43 misses entre 65 consultas; CODE: 22 hits e 8 misses entre 30; HYBRID: 4 hits e 1 miss entre 5.
- Ambas as rotas vetoriais usam consultas Qdrant filtradas por projeto e demais escopos e impõem `query.top_k` ao resultado. Diversos chunks de um mesmo arquivo podem ocupar vagas distintas: o limite atual e de chunks, nao de caminhos de fonte.
- A matriz anterior tambem revelou falhas de classificacao e consulta lexical, tratadas em B/C. Esses ajustes ainda nao foram reexecutados de modo integrado com os vetores.

## Decisao de engenharia
**Nenhuma alteracao de embeddings ou chunking nesta subfase.** Ausencia de caminho no top 10 nao prova defeito do modelo ou do chunking; precisariamos consultar resultados em profundidade e distinguir fonte nao indexada, fonte depois do top-k, e representacao inadequada. Trocar algoritmo sem essa evidencia seria ajuste especulativo de relevancia. Esta subfase fecha como diagnostico vetorial documentado; a recuperacao de qualidade geral nao esta fechada.

## Encaminhamento
- RAG-017-E: avaliar overfetch, diversidade de fontes, RRF e deduplicacao com teste A/B controlado e sem enfraquecer filtros ou limites de seguranca.
- RAG-017-F: repetir o benchmark integrado com o corpus e modelos reais, manter limiares congelados.
- O indice de producao permanece NOT READY/BLOCKED.

## Regressao e rastreabilidade
- `tests/test_rag_017_d_vector_diagnostic.py` comprova cobertura 100/100, limites por lista e derivacao dos contadores.
- Suite RAG completa, revisao diff e Git devem ser executados antes de fechar.
