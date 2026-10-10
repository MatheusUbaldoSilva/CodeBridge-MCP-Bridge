# RAG-017 — Gate estrutural para atualização do MCP instalado

Diagnóstico de 2026-10-10: o NSIS `installer/CodeBridge.nsi` copia `author_mcp/mcp_server.py`, mas não cria/copia a árvore `rag/`. A instalação existente tampouco contém `rag/`. O script instalado em 06/10/2026 não anuncia `codebridge_rag_status`; o repositório atualizado anuncia. **Não atualizar apenas o arquivo MCP isoladamente**: suas dependências RAG podem faltar.

Incluído `benchmarks/rag017_installer_preflight.py`, verificador somente leitura, fail-closed, com dois testes. Ele detecta se a receita NSIS declara destino e cópia recursiva do RAG, além da presença da ferramenta de status no código-fonte. Esta é uma checagem **estrutural**, não valida dependências Python, build resultante, segurança, reversão ou implantação.

Próxima etapa de engenharia: construir pacote experimental isolado com todos os módulos RAG e dependências, validar imports e execução MCP em porta de teste; revisar mecanismo de rollback do instalador e configuração do updater. Só após auditoria da compatibilidade e cópia de segurança, planejar atualização controlada do instalado. Nunca promover o modelo Code-only automaticamente; manter flags experimentais falsas. RAG-017-J BLOCKED, holdout independente pendente.
