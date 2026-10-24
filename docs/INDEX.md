# Documentação principal — CodeBridge

Referência técnica do **estado atual** de `rag-017-optimized-inference-after-candidate`. Este conjunto descreve componentes, funções, contratos, permissões e restrições reais do código e da instalação conectada — não uma cronologia de implementação.

## Referências oficiais

| Documento | Escopo |
|---|---|
| [CURRENT_SYSTEM.md](CURRENT_SYSTEM.md) | Produto, arquitetura, componentes e estado operacional |
| [EXECUTION_RUNTIME_CURRENT.md](EXECUTION_RUNTIME_CURRENT.md) | Executor CBMCP/1, terminais, ledger, execução e limites |
| [MCP_TOOLS_CURRENT.md](MCP_TOOLS_CURRENT.md) | Ferramentas MCP, assinaturas, campos e exemplos de chamadas |
| [SECURITY_AND_PERSISTENCE_CURRENT.md](SECURITY_AND_PERSISTENCE_CURRENT.md) | Windows Credential Manager, DPAPI, Named Pipes, mutex, SQLite e autorização |
| [RAG_CURRENT.md](RAG_CURRENT.md) | Estado público do RAG, leitura, pesquisa e admissão de fontes |
| [RAG_INTERNALS_CURRENT.md](RAG_INTERNALS_CURRENT.md) | Inventário, chunking, modelos, SQLite/FTS5, Qdrant, ranking, gerações e gates |
| [DESKTOP_FEATURES_CURRENT.md](DESKTOP_FEATURES_CURRENT.md) | Interface, terminais, telemetria, GPU, sons e painel de conhecimento |
| [DESKTOP_DEPLOYMENT_CURRENT.md](DESKTOP_DEPLOYMENT_CURRENT.md) | Instalação e configuração do aplicativo Windows |
| [OPERATIONS_AND_RECOVERY_CURRENT.md](OPERATIONS_AND_RECOVERY_CURRENT.md) | Diagnóstico, NSIS, runtime, proteção de dados e recuperação |

O [README](../README.md) apresenta o produto e encaminha para esta documentação.

## Interpretação obrigatória

- **Implementado:** existe na branch, ainda que possa não estar habilitado no aplicativo.
- **Observado operacional:** comprovado por chamada/status da instalação.
- **Condicional:** depende de configuração, permissões ou conexão.
- **Não liberado / não certificado:** existência do código não autoriza uso no índice/instalação ativos.
- **Conforme observado em:** identificadores de geração, quantidades e disponibilidade de processos são exemplos de estado e podem mudar.

A API MCP anunciada à conexão pode ser um subconjunto do servidor. O código da revisão Git e as ferramentas efetivamente anunciadas são as referências finais para assinatura/uso. Use os campos de status para avaliar disponibilidade.

## Conservação dos dados e referências

A documentação antiga só pode ser retirada após verificação de dependências em código/testes, arquivo de recuperação e auditoria final. O índice RAG atualmente publicado pode continuar citando versões antigas até que a indexação incremental autorizada esteja funcional. A consolidação documental não modifica nem apaga o índice ativo.
