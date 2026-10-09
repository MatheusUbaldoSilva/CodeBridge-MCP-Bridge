# RAG-017-F — Anti-overfit e regressão integrada

## Escopo
Executar o benchmark semântico completo com os modelos Jina locais, FTS5, Qdrant Local, fusão RRF e deduplicação, usando as 100 perguntas e o ground truth congelados do RAG-014. Preservar critérios de produção, evitar ajustes por query ID e verificar regressões.

## Medição real
Os resultados foram obtidos pelo runner original importado sem mudanças em `benchmarks/run_rag017f_regression.py`. A saída foi redirecionada para `benchmarks/rag017f_semantic_latest.json`, sem sobrescrever o benchmark RAG-014.

| Indicador | Referência congelada | RAG-017-F | Meta |
|---|---:|---:|---:|
| Recall@5 | 0,46 | **0,77** | 0,80 |
| Recall@10 | 0,48 | **0,83** | 0,90 |
| MRR | 0,32578 | **0,53182** | 0,60 |

Diferenças observadas: +31 pontos percentuais no Recall@5 e +35 pontos no Recall@10; MRR +0,20604. **O corpus mudou**: referência 179 documentos / 6994 chunks; replay 205 documentos / 8726 chunks. Esses deltas não são estimativas causais controladas sobre corpus idêntico.

A distribuição observada de rotas no replay foi CODE=38, TEXT=58, HYBRID=4, conforme alterações gerais da fase C.

## Independência do gate
O script `benchmarks/evaluate_rag017f_gate.py` reconstrói Recall@5, Recall@10 e MRR a partir do ground truth e dos caminhos retornados, e compara com as três metas originais presentes em `benchmarks/rag014_readiness_report.json`.
- Resultado da qualidade: **BLOCKED**; os três indicadores continuam abaixo do piso.
- Índice de produção: não é declarado READY; o benchmark usa índice temporário.
- Nenhuma regra específica para as 100 perguntas, nenhum relaxamento de threshold e nenhuma modificação dos modelos foi incluída nesta subfase.

## Anti-overfit e regressão
- `tests/test_rag_017_f_regression.py` testa os 100 IDs únicos, ground truth íntegro, métricas recalculadas e limites originais preservados.
- Executar suite RAG completa, validação Python, revisão diff, commit, push e pós-commit.
- Próximas fases G/H devem conectar executores e provar índice persistente; **não** considerar produção liberada mesmo com G/H enquanto o gate de qualidade estiver bloqueado.

## Estado
Subfase F concluída como **avaliação e regressão**, não como liberação de qualidade. Melhorias adicionais para alcançar os pisos exigem investigação e nova medição sem overfit.
