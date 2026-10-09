# RAG-017 — Seleção diversificada de passagens

## Intervenção
Implementado seletor determinístico `rag/ranking/passage_diversity.py`. Preserva o primeiro trecho mais bem ranqueado, seleciona os demais por novidade lexical de tokens com Jaccard, até três passagens e documento/projeto/branch únicos. Disponível somente via `diverse=True` no multi-passage, padrão `False`. Não houve alteração no executor de produção.

## Benchmark real
`benchmarks/evaluate_rag017_diverse_passage.py`: 100 queries congeladas, índice persistente existente, embeddings Jina e BGE cross-encoder GGUF local. `benchmarks/rag017_diverse_passage_evaluation.json`.

| Estratégia | Recall@5 | Recall@10 | MRR | p95 adicional |
|---|---:|---:|---:|---:|
| Ranking por documento | .82 | .91 | .596595 | — |
| Multi-passage original | .80 | .90 | .549897 | 757ms |
| Seleção diversificada | **.72** | **.88** | **.479226** | 812ms |

Decisão: **REJEITAR ativação**. Os três indicadores pioraram frente ao melhor baseline. Não há holdout independente, e a latência extra do BGE não equivale à latência fim a fim.

## Estado
Índice persistente READY; gate de produção BLOCKED; thresholds congelados inalterados. O experimento fica auditável, não integrado ao MCP instalado. Antes do RAG-017-J, priorizar avaliação independente de recuperação por documento e representações estruturais, sem otimizar as mesmas 100 queries.
