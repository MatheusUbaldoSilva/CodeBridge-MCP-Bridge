# RAG-017 — Correção do gate: investigação de reranking

## Objetivo
Corrigir o gate de produção antes de RAG-017-J, sem reduzir Recall@5 >= 0.80, Recall@10 >= 0.90 ou MRR >= 0.60. O estado persistente permanece READY; a liberação geral permanece BLOCKED.

## Teste feito
`benchmarks/explore_rag017_rerank.py` usa o mesmo índice persistente, 100 queries do benchmark congelado e os modelos locais Jina. Compara recuperação com depth 32, fusão RRF e seleção de caminhos distintos, variando o peso de sobreposição de tokens da pergunta com caminho/conteúdo. Guarda resultados em `benchmarks/rag017_quality_rerank_exploration.json`.

**Melhor alternativa testada nesta investigação:** sem peso de reranking lexical (weight=0): Recall@5 = 0.80, Recall@10 = 0.88, MRR = 0.50483. Acrescentar peso lexical degrada os resultados, chegando a Recall@5 = 0.64 e Recall@10 = 0.72 em uma variante.

Os resultados anteriores em `rag017_quality_ablation.json` indicam até Recall@5 de 0.81 e Recall@10 de 0.89 em **configurações diferentes**. Nenhuma variante cumpre simultaneamente os três thresholds.

## Auditoria de cobertura das fontes
`benchmarks/audit_rag017_ground_truth_coverage.py` examinou o SQLite persistente e comprovou **0/100 perguntas cujo conjunto de fontes esperadas está inteiramente ausente**. Artefato: `benchmarks/rag017_ground_truth_coverage.json`. Assim, na medição atual, o principal desafio é recuperar e ordenar o conteúdo existente, não ingestão das fontes do ground truth.

## Decisão
**Não aplicar o reranker por overlap de palavras, pois houve regressão.** Nenhuma mudança de algoritmo foi aplicada em produção. Os pesos da busca, critérios e índice persistente permanecem inalterados.

## Próximos requisitos para liberar o gate
- Avaliar reranking semântico com candidatos diversificados, rank de documento/caminho e possíveis duplicidades, preservando filtros de projeto e segurança.
- Criar conjunto de validação independente do benchmark usado para escolher variantes, evitar regras especiais por ID e medir também latência, RAM e VRAM.
- Executar nova avaliação real após correção aprovada, exigindo **os três thresholds simultaneamente**; somente então retirar BLOCKED.
