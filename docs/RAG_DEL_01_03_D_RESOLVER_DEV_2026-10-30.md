RAG-DEL-01.03-D — Resolver de geracao privada RAG_DEL_01 (DEV)
Data 2026-10-30
Ramo explicitamente separado no isolated_project_index.py. Novo validador verifica transaction ID, diretorio del_<id>, recibo SHA256, projeto, snapshot, fonte, hashes SQLite/manifesto, inventario fisico Qdrant fechado e progress.json com contagens iguais. Negativas falham fechado; nao publica catalogo. Nao cria automaticamente recibos operacionais nem autoriza exclusao. O indice RAG_AUTO_03 existente permanece com o caminho antigo.
