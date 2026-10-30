# RAG-DEL-01.04-DJ — Inventário público protegido e auditoria MCP/GUI (DEV)

## Constatações de código-fonte

- author_mcp/rag_bridge.py: as rotas públicas codebridge search_rag_context e get_rag_context usam production_generation_read() enquanto consultam SQLite e semântica. get_rag_status protege o ramo público quando há índice existente. O próprio bridge contém inspect_rag_generation_readers para verificar implementação carregada, mas esta sessão NAO atestou o processo MCP instalado nem todas as rotas legadas.
- rag/runtime/context_service.py: get_context com sqlite_path explícito aceita a geração já pinada. Sem sqlite_path, a função resolve o índice de legado diretamente; chamadas diretas fora do bridge exigem auditoria separada.
- app_rewrite/rag_panel.py: a operação documents ainda resolve o SQLite público via resolve_rag_sqlite_path() e consulta sem production_generation_read. Esse arquivo tinha alterações preexistentes e não foi sobrescrito ou stageado nesta sessão.
- Caminhos de projeto privado no MCP são delegados a isolated_project_search quando cadastrados; a política de swap/deletion privado ainda não possui ativação operacional homologada.

## Implementação isolada

Novo helper read_pinned_public_document_inventory em rag/runtime/knowledge_deletion_public_inventory_read.py:

1. Aceita somente namespace público codebridge, limite de 1 a 2000.
2. Detém production_generation_read() durante toda a leitura de rag_documents, filtra por project_id e abre SQLite mode=ro com PRAGMA query_only.
3. Recusa SQLite redirecionado, journal de transição pendente e lock de geração em uso.
4. Retorna PUBLIC_DOCUMENT_INVENTORY_READ_ONLY, generation, documents, flags read_only=True, activation_authorized=False e operational_use_allowed=False.

Cinco testes em TemporaryDirectory/CodeBridge/rag verificam exclusão de outro projeto, consistência da leitura, ausência de escrita, lock Win32 exclusivo concorrente, journal pendente e caminhos malformados. Nenhum índice real foi consultado para este helper.

## Importante

Esta API AINDA NAO foi integrada ao rag_panel.py e NAO certifica o UI instalado. A alteração da GUI precisa ser revisada à parte para não sobrescrever os 5 arquivos preexistentes e para preservar o contrato do usuário. Os testes não provam que todo MCP instalado está na mesma revisão do código-fonte.

A exclusão operacional, promoção de geração, freeze da fila real, alterações na Stable e push continuam proibidos sem autorização explícita.