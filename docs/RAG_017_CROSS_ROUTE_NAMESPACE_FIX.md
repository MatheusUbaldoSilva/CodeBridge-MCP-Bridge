# RAG-017 — Correção de isolamento na fusão por documento

Ao auditar `rerank_documents`, um teste adversarial mostrou que dois resultados de **projetos diferentes com o mesmo `chunk_id`** podiam escapar da detecção de mistura de namespaces: a deduplicação acontecia antes da adição do segundo projeto ao conjunto de namespaces. Foi alterada a ordem da checagem de `result.metadata.project_id`, que agora é registrada antes da deduplicação. A fusão mantém a política **fail-closed** e rejeita dados de projetos diferentes.

Testes novos cobrem projetos distintos, `chunk_id` igual entre projetos, preservação de ramificações Git e separação de documentos por caminho. Regressão RAG: **792 testes aprovados**. A alteração é no reranker da branch experimental, não implica ativação do Code-only no serviço e não substitui auditoria de filtros na camada de recuperação. Build candidata dual continua protegida. Gate de produção **BLOCKED**.
