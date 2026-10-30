RAG-DEL-01.03-G - Auditoria semantica de Qdrant em staging isolado (DEV)
Compara os vetores sobreviventes com manifesto e SQLite, em lotes limitados de 256. Verifica IDs, metadados, SHA, dimensoes e contagem integral incluindo vetores extras. Recebe cliente Qdrant fornecido pelo chamador; nenhuma colecao ativa e aberta nem gravada. Testes unitarios negativos e E2E de cinco vetores, tres lotes, aprovados. Nao autoriza ativacao.

