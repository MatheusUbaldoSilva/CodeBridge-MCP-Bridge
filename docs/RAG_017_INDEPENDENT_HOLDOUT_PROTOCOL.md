# RAG-017 — Protocolo para holdout independente

Este marco adiciona `benchmarks/rag017_independent_holdout_gate.py`, um avaliador de resultados para um conjunto de perguntas congelado por SHA-256. As entradas são `questions.jsonl` (id, query), `labels.jsonl` (id, expected_paths, review_status, reviewer_id) e `results.jsonl` (id, paths ordenados). A checagem rejeita hash divergente, IDs duplicados, cobertura incompleta, fontes esperadas vazias e linhas marcadas como não revisadas. Métricas: Recall@5 >= 0,80, Recall@10 >= 0,90 e MRR >= 0,60.

**Este mecanismo não cria um holdout independente** e os valores dos metadados de revisão não constituem prova de revisão externa. É necessário que um revisor que não tenha participado dos ajustes do RAG formule/verifique e congele as perguntas e fontes esperadas antes de executar as predições. As 100 perguntas RAG-014 e as 20 shadow já usadas em desenvolvimento não contam. Auditoria de proveniência e sobreposição com conjuntos anteriores deve ocorrer antes do gate final.

O retorno `quality_passed` se refere exclusivamente a métricas do conjunto fornecido; `production_approved` permanece sempre false. Mesmo com qualidade aceita, RAG-017-J permanece BLOCKED até integração, limites de memória, robustez e p95 aprovados. A build dual permanece preservada na tag `rag-017-candidate-cross-route-quality-20261009`; não ativar produção.
