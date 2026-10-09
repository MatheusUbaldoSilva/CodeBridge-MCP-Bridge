# RAG-017 — Diagnóstico hierárquico de recuperação (pós 97b39fd)

## Experimento real de 100 consultas
O script `benchmarks/diagnose_rag017_hierarchical_recall.py` usa Jina Text e Code sobre o mesmo índice persistente (somente leitura) e o ground truth congelado de RAG-014. Os resultados estão em `benchmarks/rag017_hierarchy_diagnostic.json`.

| Depth de candidatos por modalidade | Cobertura-oráculo da fonte correta |
|---:|---:|
| 5 | 81% |
| 10 | 88% |
| 20 | **96%** |
| 32 | 96% |

A cobertura-oráculo é o teto condicionado a uma fonte correta estar **presente entre os candidatos**, não a taxa real de recall do resultado final: pressupõe uma ordenação perfeita. A cobertura estabiliza em 96% nos depths testados.

## Experimento de votação por documento
Usamos deduplicação por caminho dentro de cada lista lexical/vetorial e RRF no primeiro aparecimento da fonte, somando sinais por modalidade.

| Depth | Recall@5 | Recall@10 | MRR |
|---:|---:|---:|---:|
| 10 | 0.82 | 0.88 | 0.541397 |
| 20 | 0.79 | 0.89 | 0.545810 |
| 32 | 0.77 | 0.89 | 0.541298 |

O melhor baseline anterior `rag017_semantic_document_reranker_evaluation.json` permanece superior: Recall@5 0.82, Recall@10 0.91 e MRR 0.596595. A votação simples não é uma correção validada.

## Diagnóstico e próximos critérios
- O gargalo predominante entre as fontes disponíveis é **ranking de documentos**; não basta aumentar candidatos ou combinar votos simples.
- Há 4/100 consultas que não encontram nenhuma fonte esperada até depth 32 nas listas coletadas; tratá-las como falhas distintas de recuperação/cobertura dos candidatos.
- A comparação ainda utiliza o mesmo benchmark explorado repetidamente: uma configuração futura que passe essas 100 consultas **não estará automaticamente pronta para produção**. É necessário holdout independente e avaliação simultânea de qualidade/latência/recursos.
- Próximo teste deve contrastar modelos de classificação por documento e uma representação estrutural de código sem usar regras por ID de pergunta. Não rebaixar Recall@5 0.80, Recall@10 0.90 nem MRR 0.60.
- Não foi aplicada nenhuma alteração ao ranking de produção, ao SQLite persistente ou ao MCP instalado. **READY técnico / gate BLOCKED**.

## Fechamento
Registrar testes, diff, commit e push; RAG-017-J permanece não iniciado enquanto a qualidade estiver pendente.
