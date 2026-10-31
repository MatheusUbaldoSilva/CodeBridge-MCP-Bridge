# RAG-DEL-01.04-DQ-A — Entrada de leitores privados (DEV)

Estado: mapeamento de fonte concluido, ativacao operacional NAO autorizada.

## Contrato observado

- GUI public documents: read_pinned_public_document_inventory agora usa production_generation_read durante a leitura SQLite (DL).
- GUI private documents: rag_panel.py resolve isolated_project_index e le SQLite sem mutex de catalogo retido.
- MCP public search/context: rag_bridge.py usa production_generation_read, mas o processo instalado nao foi atestado.
- MCP private search/context: isolated_project_search.py valida catalogo/sha e depois usa SQLite sem catalog mutex persistente.
- Semantic private: semantic_isolated_project adquire lock semantic internamente durante subprocesso. Guard externo nao pode readquirir semantic sem um contrato explicito.
- Lab deletion writer: generation exclusivo -> semantic exclusivo -> queue BEGIN IMMEDIATE -> catalog mutex. Heartbeats devem poder renovar enquanto semantic estiver ocupado.
- Catalog mutex atual: auto_index_canary._catalog_mutex usa msvcrt.LK_LOCK sem timeout; inadequado como guard direto de GUI sem adaptacao.

## Proximas letras

DQ-B: implementar guard TEMP com tentativa de lock e timeout finito.
DQ-C: proteger busca privada inteira sem duplo lock semantic e provar consistencia de SQLite/Qdrant.
DQ-D: testes Win32 entre processos, crash, journal e rollback.
DQ-E: atestar MCP instalado e GUI, integrar somente apos homologacao e autorizacao.

Criterios: nunca autorizar exclusao real no laboratorio; nao tocar em fila real, indice publico, Stable ou GitHub. Validar cada fase com testes, patch notes e commit seletivo.