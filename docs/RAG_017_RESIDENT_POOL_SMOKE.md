# RAG-017 — Pool residente experimental

Consulta inicial: 13942 ms. Consultas seguintes: 6286, 5992, 5766 e 4520 ms.

A meta warm p95 continua 1000 ms; o experimento falhou. As cinco medições não representam p95 estatístico. Qualidade exploratória cross-route anterior: Recall@5 0.89, Recall@10 0.95, MRR 0.7048, sem holdout independente. Pico simultâneo de RAM/VRAM não validado.

Pool disponível apenas via experimental_resident_models=True; padrão False. O benchmark fechou as instâncias Jina ao terminar. Nenhuma mudança no índice, instalador ou integração MCP.

Gate BLOCKED. Próxima ação: decompor latência por embedding, armazenamento e ranking, depois validar orçamento e dataset independente.
