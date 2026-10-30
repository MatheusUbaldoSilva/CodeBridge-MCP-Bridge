RAG-DEL-01.05 — Controlador de revisao somente leitura (DEV)
Data 2026-10-30
knowledge_deletion_review.py recebe projeto e arquivos selecionados, consulta preview_knowledge_removal, valida projeto privado e a resposta fail-closed. Produz texto com geracao, quantidade de documentos/chunks e hash de revisao. Nao autoriza ou executa exclusao. 5 testes temporarios aprovados.
Integracao GUI pendente e nenhuma alteracao em rag_panel.py preexistente.
