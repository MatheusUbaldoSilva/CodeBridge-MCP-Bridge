# RAG-017-A — Diagnóstico das 100 queries

## Escopo e política
Etapa de diagnóstico do handoff RAG-017. Nenhum algoritmo de classificação, chunking, retrieval, embeddings, fusion ou dedup foi modificado. Nenhuma meta de produção foi reduzida. O gate de produção continua **BLOCKED**.

## Evidências congeladas e replay
- Benchmark congelado de referência: `benchmarks/rag014_semantic_benchmark_latest.json` — 100 queries; Recall@5 0.46; Recall@10 0.48; MRR 0.32577778.
- Replay instrumentalizado em 08/10/2026: `benchmarks/rag017_replay_latest.json` — 100 queries; Recall@5 0.46; Recall@10 0.47; MRR 0.32227778.
- O corpus evoluiu desde a referência: de 179 documentos / 6994 chunks para 200 documentos / 8683 chunks. A diferença de 1 pp no Recall@10 é **observada**, não atribuída causalmente a essa mudança.
- O script `benchmarks/trace_rag017_a.py` executa o runner sem alterar o código original, registra a rota e as listas lexical, text-vector, code-vector, RRF e final até top 10 por query. Os dados de rastreamento estão em `benchmarks/rag017_component_trace.json`.
- A matriz resultante de 100 consultas está em `benchmarks/rag017_failure_matrix.json`; geração por `benchmarks/finalize_rag017_a.py`.
- Matriz preliminar extraída do benchmark congelado: `benchmarks/rag017_failure_matrix_initial.json`, obtida por `benchmarks/analyze_rag017_a.py`.

## Resultado por estágio
- **46/100** queries encontram fonte esperada no top 5 (HIT_TOP5).
- **1/100** só encontra no ranking 6–10 (TOP_K_5_CUTOFF).
- **52/100** não encontram a fonte esperada no top 10 de nenhum dos três candidatos analisados (RETRIEVAL_CANDIDATE_MISS).
- **1/100** tem fonte esperada no RRF top 10 mas não no resultado final top 10 (DEDUP_OR_TOP_K_CUTOFF).
- Total: **47/100** acertos no top 10; **53/100** consultas sem fonte esperada no top 10.

## Interpretação e limites
As categorias acima identificam **o estágio observável da falha**, não a causa-raiz. O top 10 de cada componente não basta para afirmar se houve tokenização inadequada, rota errada, embeddings fracos, chunking, perda na fusão ou ausência de fonte. Não houve ajuste para IDs específicos de queries. Os limiares permanecem Recall@5 >= 0.80, Recall@10 >= 0.90, MRR >= 0.60, mais índice persistente READY.

## Priorização para as próximas subfases
1. **RAG-017-B**: investigar normalização e ranking lexical nas 52 perdas já presentes na coleta de candidatos. Comparar top lexical com metadados e presença da fonte no índice; separar ausência de fonte de ausência de match.
2. **RAG-017-C**: analisar rotas TEXT/CODE/HYBRID por query e quantificar eventuais erros de classificação, sem regras especiais por ID.
3. **RAG-017-D**: avaliar chunking e embeddings nos grupos TEXT e CODE com ground truth preservado.
4. **RAG-017-E**: inspecionar RRF, dedup e cortes de top K, especialmente a query que aparece no RRF mas desaparece no final.
5. **RAG-017-F**: regressão completa após cada mudança; metas congeladas.

## Testes e segurança
- Runner real com modelos Jina locais, SQLite FTS5 e Qdrant Local, sem conexão de índice de produção.
- Trilha completa das 100 queries; validação contra os IDs do dataset e do ground truth.
- Testes automatizados de integridade: `tests/test_rag_017_a_matrix.py`.
- Suite RAG: testes executados no Windows com `python -m unittest discover -s tests -p test_rag_*.py -q`.
- Execução permanece limitada ao benchmark temporário: nenhuma migração, limpeza, alteração do índice de produção ou threshold foi realizada.
