# RAG-017 — Alternativa de menor custo (CODE-only)

A build candidata principal permanece congelada na tag `rag-017-candidate-cross-route-quality-20261009`, commit `b859d0871a45163a695899e955f9be39c0e29b3a`. Essa tag deve permanecer intacta. A investigação seguinte roda na branch `rag-017-optimized-inference-after-candidate`.

Benchmark exploratório: 100 consultas RAG-014 previamente utilizadas; mesmo índice persistente e ground truth. Resultado da ablação:

| Recuperação | Recall@5 | Recall@10 | MRR |
|---|---:|---:|---:|
| Original por documento | 0.82 | 0.91 | 0.596595 |
| Lexical + Jina Code | 0.88 | 0.92 | 0.692944 |
| Lexical + Text + Code | 0.89 | 0.95 | 0.704806 |

A alternativa CODE-only evita a inferência Jina Text no caminho de consulta, mas **não comprova o orçamento de warm p95 1000ms**, pois a inferência Jina Code sozinha apresentou latência acima do teto nas medições anteriores. Não é validação independente. Não ativar em produção nem reduzir thresholds.

Próxima etapa: medir Code-only fim a fim em serviço persistente supervisionado e memória segura, gerar holdout independente e verificar cobertura de fontes de prosa. Gate ainda BLOCKED.
