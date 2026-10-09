# RAG-017 — Code-only warm experiment

Branch: `rag-017-optimized-inference-after-candidate`. A build dual permanece protegida pela tag anotada `rag-017-candidate-cross-route-quality-20261009`, que aponta para b859d08. Este experimento não altera a tag.

Executor real com QueryRoute.CODE, experimental_cross_route=True, experimental_resident_models=True. Apenas o processo Jina Code foi carregado, e o objeto Qdrant foi reutilizado em um processo Python isolado. A aplicação instalada não foi modificada.

Primeiro smoke de cinco consultas: cold 3066.50ms; warm 64.47, 83.93, 77.65, 72.79ms. Segundo smoke com 12 consultas novas: cold 3087.65ms, 11 warm entre 60.67 e 113.57ms, p95 amostral por nearest rank 113.57ms. Isso é promissor, mas insuficiente para certificar p95 de produção, concorrência ou memória pico.

Qualidade exploratória sobre 100 perguntas anteriores: Lexical + Jina Code Recall@5=0.88, Recall@10=0.92, MRR=0.692944. Dual Text + Code preservada: 0.89/0.95/0.704806. Não existe validação independente de qualidade. Não há garantia de equivalência no comportamento de roteamento automático original, já que o benchmark de latência forçou QueryRoute.CODE.

**Gate BLOCKED**. Antes de ativar: criar holdout rotulado independente e congelado, adaptar caminho CODE-only com política de filtros e isolamento testados, instrumentar p95 warm e cold com amostras suficientes, medir VRAM/RAM pico e concorrência, validar lifecycle Qdrant supervisionado, realizar auditoria Git completa. Não reduzir thresholds de qualidade ou performance.
