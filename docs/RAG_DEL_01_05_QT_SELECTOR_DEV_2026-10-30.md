RAG-DEL-01.05 - Componente Qt de selecao (DEV)
Data 2026-10-30
KnowledgeRemovalSelector recebe inventario validado, permite selecionar varios arquivos e emite somente pedido de PREVIA. Nao possui funcao de excluir ou acesso a SQLite/Qdrant. Testes offscreen Qt cobrem selecao exata, inventario renovado e nenhuma selecao.
Ainda NAO integrado ao rag_panel.py, porque a branch tem alteracoes preexistentes; essa integracao exige auditoria/approval e backend operacional homologado.
