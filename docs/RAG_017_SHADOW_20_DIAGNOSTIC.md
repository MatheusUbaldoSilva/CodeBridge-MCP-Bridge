# RAG-017 — Avaliação adicional de 20 perguntas

Na branch experimental, criamos 20 perguntas diferentes das 100 questões RAG-014, cada uma associada a um arquivo-fonte esperado. O conjunto foi gerado por inspeção das áreas do projeto, portanto NÃO é holdout independente pré-registrado. A anotação é de tipo `SEEDED_FROM_SOURCE_LOCATIONS` e não substitui avaliação cega por revisor independente.

Resultado obtido no índice persistente com Jina Code residente, fusão lexical + code e Qdrant reutilizado: Recall@5 **0,90**, Recall@10 **0,95**, MRR **0,725476**. Uma consulta não encontrou a fonte esperada entre os primeiros 10 (`rag017-shadow-007`, módulo `rag/ranking/semantic_document_reranker.py`); investigar esse caso sem adaptar especificamente as regras a ele. A primeira consulta levou 3753,66 ms, as demais 68–117 ms neste ensaio.

Arquivos: `benchmarks/rag017_shadow_20_queries.jsonl`, `benchmarks/evaluate_rag017_shadow_20.py`, `benchmarks/rag017_shadow_20_results.json`. O arquivo local `benchmarks/rag017_code_only_extended_smoke.json` foi modificado por execução anterior e NÃO deve ser incorporado automaticamente.

Gate permanece BLOCKED: ainda faltam holdout cego rotulado independentemente, amostra estatística representativa de p95, pico simultâneo de RAM/VRAM, isolamento e falhas sob carga e lifecycle/serviço estável. Limiares originais não foram modificados. A tag `rag-017-candidate-cross-route-quality-20261009` permanece protegida.
