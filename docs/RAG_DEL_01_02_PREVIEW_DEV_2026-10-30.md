# RAG-DEL-01.02 — Prévia somente leitura (DEV)
Data: 2026-10-30
Status: IMPLEMENTADO EM LABORATÓRIO; sem ação de exclusão.

## Implementação
- rag/runtime/knowledge_deletion_preview.py
- tests/test_rag_del_01_02_preview.py

A API preview_knowledge_removal(project_id, paths) consulta exclusivamente geração privada habilitada via resolve_isolated_project, que valida recibos e hashes da geração antes de liberar caminhos.
Seleção explícita e canônica: recusa vazia, repetida, absoluta, travessia de diretórios, projeto público e caminhos ausentes.
Confere integridade SQLite, inventário de documentos/chunks e contagens contra manifesto versionado. Retorna projeto, geração, revisão, caminhos ordenados, documentos e chunks a remover/preservar e fingerprint SHA-256 da solicitação.
Resultado é informativo: deletion_authorized=False, candidate_created=False, public_pointer_updated=False, source_files_modified=False.
Não abre Qdrant, não altera SQLite, não grava catálogo, não inicia job e não apaga fontes.

## Limites obrigatórios
O fingerprint desta prévia não é token de consentimento e não autoriza executor.
Na próxima etapa, incluir revalidação de revisão de geração, payloads Qdrant, sha de conteúdos e manifesto em operação separada antes da cópia; nenhuma prévia substitui prova integral de geração.
Testes atuais usam SQLite temporário e manifesto simulado: **não houve teste em índice pessoal real**.
Não alterar Stable nem ponteiro público.

## Evidências
10 testes de prévia PASS em pasta temporária, inclusive seleção válida, recusa de projeto público, caminho inválido, índice inexistente, integridade SQLite, identidade de geração e divergências no manifesto.
