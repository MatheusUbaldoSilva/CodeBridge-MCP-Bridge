# RAG-017 — Reranker semântico por documento (experimental)

## Implementação
`rag/ranking/semantic_document_reranker.py` cria um ranking por documento/caminho, agregando sinais de listas de recuperação lexical e vetorial Jina, com atenuação de chunks repetidos, namespace por projeto e desempate determinístico. Não é um cross-encoder dedicado: a relevância semântica é proveniente dos embeddings Jina recuperados pelos vetores. O módulo não foi ativado no pipeline instalado, que permanece inalterado.

## Benchmark real
`benchmarks/evaluate_rag017_semantic_document_reranker.py` avalia as 100 consultas congeladas sobre **o mesmo índice persistente** do CodeBridge, consultando Jina Text e Code. Artefato: `benchmarks/rag017_semantic_document_reranker_evaluation.json`.

| Variante | Recall@5 | Recall@10 | MRR |
|---|---:|---:|---:|
| Documento k=10 | 0,82 | 0,91 | 0,596595 |
| Documento k=15 | 0,83 | 0,91 | 0,587845 |
| Documento k=20 | 0,83 | 0,91 | 0,584325 |

Metas congeladas: Recall@5 >= 0,80; Recall@10 >= 0,90; MRR >= 0,60. **Nenhuma configuração atingiu as três simultaneamente**.

## Riscos e pendências
- O mesmo benchmark foi usado para explorar opções e medi-las: existe risco de overfitting. Não houve validação independente em novas perguntas.
- Não foi avaliada a regressão integrada de cold/warm/RAM/VRAM para habilitar o reranker no executor real.
- O algoritmo soma evidência lexical + vetorial por documento; múltiplos trechos relevantes de um mesmo arquivo podem ser úteis em respostas longas. Testar recuperação de chunks e citabilidade.
- O índice persistente permanece READY, mas o gate de **produção BLOCKED**.
- Próxima avaliação: dataset independente, testes de desempenho e possível segundo estágio de reranking com modelo específico ou representação documental, sem reduzir os critérios.

## Fechamento
Testes de contrato e regressão RAG completos, diff, commit, push e auditoria pós-commit. O módulo permanece opt-in/não ativado.
