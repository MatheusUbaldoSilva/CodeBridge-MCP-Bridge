# RAG-017 — Triagem de similaridade entre perguntas

Incluído `benchmarks/audit_rag017_semantic_overlap.py`: triagem heurística para comparação do futuro holdout com RAG-014 e shadow-20. Usa normalização de texto, similaridade por tokens (Jaccard) e sequência (`SequenceMatcher`) com limiar diagnóstico padrão de 0,78. Registra pares sinalizados para revisão humana.

**Não é detector semântico baseado em embeddings**, não cobre todas as paráfrases e pode produzir falsos positivos ou falsos negativos. A ausência de flags nunca certifica independência; `independence_certified` permanece `false`. Nenhum resultado deve ser usado para ajustar o ranking com base no futuro holdout.

A autoria e revisão independentes e a avaliação cega de qualidade permanecem pendentes. Gate de produção BLOCKED. Build dual preservada na tag `rag-017-candidate-cross-route-quality-20261009`; thresholds inalterados.
