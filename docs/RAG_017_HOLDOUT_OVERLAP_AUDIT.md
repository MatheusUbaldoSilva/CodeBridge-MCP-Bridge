# RAG-017 — Auditoria de sobreposição do holdout

Adicionado `benchmarks/audit_rag017_holdout_overlap.py` para detectar perguntas repetidas após normalização de maiúsculas/minúsculas e espaços, comparando um futuro holdout com conjuntos de perguntas já usados (RAG-014 e shadow-20). Em caso de colisão, o comando retorna erro, com IDs e fontes relacionadas. Testes cobrem sobreposição, duplicidade interna e perguntas novas.

Este é um filtro de duplicação **exata normalizada**. Não detecta paráfrases, questões semanticamente semelhantes, vazamento de arquivos-fonte ou falta de independência do revisor. O resultado `independence_certified` permanece sempre falso. A revisão realmente independente continua obrigatória.

Nenhuma alteração no índice, modelos, thresholds ou na build dual preservada. Gate de produção BLOCKED.
