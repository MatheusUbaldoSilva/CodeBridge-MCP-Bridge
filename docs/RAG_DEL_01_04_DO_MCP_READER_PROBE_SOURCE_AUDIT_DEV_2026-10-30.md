# RAG-DEL-01.04-DO — Contrato de auditoria do MCP (somente fonte DEV)

## Resultado da inspeção

A implementação author_mcp/mcp_server.py contém o tool codebridge_rag_generation_probe, registrado com read_only_hint=True e structured_output=True. Ele delega a author_mcp/rag_bridge.inspect_rag_generation_readers. Essa função inspeciona os nomes das funções já carregadas, testa que um lock generation exclusivo colide com reader shared, e retorna safe_to_activate=False e child_semantic_execution_attested=False.

Na conexão atual com o CodeBridge 2.0.11-prealpha, a ferramenta não consta no conjunto de ferramentas exportadas para este chat. Portanto não foi executada no processo MCP instalado. O teste abaixo NÃO constitui atestação instalada nem confirmação de que os readers carregados são os mesmos do repositório DEV.

## Testes

Foram adicionados três testes sem dependência do pacote mcp do runtime DEV:

- mock de reader compartilhado e writer exclusivo ocupado: a rotina DEV reporta bloqueio de writer, mas nunca autoriza ativação e não atesta subprocesso semântico;
- mock sem bloqueio writer: a rotina é fail-closed e reporta PUBLIC_READER_PROBE_BLOCKED;
- análise AST do registro da ferramenta confirmando nome, saída estruturada e hint read-only, sem importar o servidor MCP ou chamar a instalação real.

Os testes não fazem network, não consultam o índice real, não iniciam workers e não escrevem no catálogo.

## Próximos bloqueios

Abertura da ferramenta no conector MCP instalado e sua execução somente leitura, prova do subprocesso semântico carregado e certificação global de leitores GUI, MCP e privados continuam necessárias antes de uma ativação. Ainda é necessário tratar a fila real READY_FOR_REVIEW por workflow autorizado, sem cancelamento automático. Não habilitar exclusão real, promover geração, alterar Stable ou fazer push como parte deste teste.