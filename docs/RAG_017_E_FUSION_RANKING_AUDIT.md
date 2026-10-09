# RAG-017-E — Auditoria de fusion, ranking e dedup

## Escopo
Revisados `rag/ranking/rrf.py` (RRF com k=60; fusao por chunk_id) e `rag/ranking/dedup.py` (deduplicacao por assinatura normalizada ou shingles). Nenhum threshold, contrato de escopo ou algoritmo de producao foi alterado.

## Experimento offline nas 100 queries congeladas
Origem: `benchmarks/rag017_failure_matrix.json` (replay semantico RAG-017-A). Artefato `benchmarks/rag017e_fusion_ablation.json` produzido por `benchmarks/audit_rag017e_fusion.py`.

| Medida | Resultado |
|---|---:|
| RRF top 5: queries com expected path | 46/100 |
| RRF top 10: queries com expected path | 48/100 |
| Final apos dedup top 5 | 46/100 |
| Final apos dedup top 10 | 47/100 |
| Politica offline um caminho por fonte, top 5 | 47/100 |
| Politica offline um caminho por fonte, top 10 | 48/100 |
| Slots duplicados por caminho no RRF top 10 | 4.41 em media |
| Fonte esperada no RRF top10 e ausente do final | 1 query |

## Diagnostico
O RRF agrega identidades de chunks, nao de documentos. Consequentemente varios chunks de um caminho podem ocupar o top 10 e reduzir a diversidade. A eliminacao simulada de caminhos repetidos dentro dos 10 ja retornados trouxe **um acerto adicional no top 5**, mas **nenhum acerto adicional no top 10**. Um caso perdeu a fonte esperada ao aplicar o dedup de conteudo, devendo ser examinado individualmente na regressao sem criar regra de query id.

Esta simulacao atua **apenas sobre caminhos** conhecidos do RRF top 10. Ela nao reordena resultados nao observados, nao executa modelos, nao mede estabilidade semantica nem representa teste A/B do pipeline inteiro. Um caminho pode legitimamente conter multiplos chunks distintos, portanto impor um resultado por arquivo pode reduzir cobertura de trechos importantes.

## Decisao
**Nao implantar mudanca especulativa de ranking/dedup agora.** A auditoria cumpriu a verificacao de RRF, top-k intermediario e diversidade e localizou um caso candidato a investigacao. Qualquer alteracao devera ser medida em comparacao controlada em RAG-017-F, usando os modelos reais e mantendo thresholds congelados. Nenhum indice de producao e ativado aqui.

## Validacao
- `tests/test_rag_017_e_fusion.py` valida cobertura, integridade das contagens e ablation offline.
- Executar suite RAG, `git diff --check`, commit, push e verificacao de working tree limpa.
