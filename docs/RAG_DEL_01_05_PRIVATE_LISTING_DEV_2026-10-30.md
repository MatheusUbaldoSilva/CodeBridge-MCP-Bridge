RAG-DEL-01.05 — isolamento da listagem privada (DEV)
Quando a geracao privada nao existe, a aba Meus arquivos retorna inventario vazio; nao consulta o indice publico como fallback. Teste mockado comprova ausencia de chamada ao resolver do SQLite publico. Patch Git inclui somente o hunk de isolamento do rag_panel.py, preservando mudancas preexistentes fora do commit.
