RAG-DEL-01.03 — Qdrant file freeze (DEV)
Data 2026-10-30
Fingerprint SHA-256 de cada arquivo fisico de um Qdrant Local fechado, com identidade de caminho relativo e tamanho. Recusa symlinks/junctions, arquivos vazios e limites ultrapassados. Uso somente leitura; nao autoriza ativacao nem substitui validacao semantica dos vetores.
Testes: arquivos temporarios e Qdrant Local real criado no laboratorio. Nao toca indice ativo.
