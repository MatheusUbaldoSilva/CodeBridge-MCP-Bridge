# Documentação principal — CodeBridge

Este diretório contém os **documentos de referência do estado atual** da branch `rag-017-optimized-inference-after-candidate`. Descrevem o que o sistema possui, suas interfaces, contratos e limites, **não a sequência de desenvolvimento**.

## Leitura recomendada

1. **[CURRENT_SYSTEM.md](CURRENT_SYSTEM.md)** — visão do produto, componentes e arquitetura em operação.
2. **[EXECUTION_RUNTIME_CURRENT.md](EXECUTION_RUNTIME_CURRENT.md)** — executor CBMCP/1, terminais, preparação, execução, espera, cancelamento e limites.
3. **[MCP_TOOLS_CURRENT.md](MCP_TOOLS_CURRENT.md)** — catálogo das ferramentas MCP, argumentos, efeitos e exemplos.
4. **[RAG_CURRENT.md](RAG_CURRENT.md)** — fontes, embeddings, SQLite, Qdrant, pesquisa, integridade e status de escrita.
5. **[DESKTOP_DEPLOYMENT_CURRENT.md](DESKTOP_DEPLOYMENT_CURRENT.md)** — interface Windows, serviços, instalação, atualizador e segurança operacional.

**[README.md](../README.md)** é a apresentação do repositório. Para detalhe técnico, priorizar os cinco documentos acima.

## Interpretação dos estados

- **Implementado:** existe no código da branch.
- **Operacional/observado:** foi verificado na instalação MCP conectada.
- **Condicional:** depende de configuração, conexão ou seleção de projeto.
- **Não liberado:** componentes podem existir, mas o caminho real de produção permanece bloqueado.
- **Não certificado:** o recurso não passou por toda a validação necessária à alegação de prontidão.

Arquivos de `docs/` fora deste conjunto continuam sendo material de apoio para auditoria enquanto permanecerem no repositório; **não alteram automaticamente a descrição do estado atual**. O código da revisão Git ativa e o status de execução são as fontes finais para comportamento e disponibilidade.

## Segurança para futura consolidação

Não excluir indiscriminadamente contratos consumidos por testes/código, esquemas, políticas, registros de integridade/rollback e evidências exigidas para certificação. A eliminação das documentações antigas é uma operação separada e requer análise de dependências, backup recuperável e validação pós-exclusão. Um índice RAG ativo pode manter referências históricas até nova indexação autorizada.
