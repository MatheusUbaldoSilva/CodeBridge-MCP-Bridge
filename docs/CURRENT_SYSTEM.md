# CodeBridge — Sistema atual

> Referência técnica da branch `rag-017-optimized-inference-after-candidate`. Documento de **estado e comportamento**, não de histórico. Consulte os demais documentos principais para contratos detalhados.

## Produto

CodeBridge 2.0 — MCP Bridge é um aplicativo Windows que disponibiliza terminais locais e contexto de código/documentos a um cliente MCP autorizado, como o ChatGPT.

Componentes presentes no repositório:

- `app_rewrite/`: interface PySide6, terminal, preferências, gerenciamento MCP e painel de conhecimentos.
- `author_mcp/`: servidor MCP autoral, integração com adapter, ferramentas, protocolo e ponte RAG.
- `rag/`: inventário, chunking, modelos de embeddings, índices, recuperação e controles de execução/publicação.
- `installer/`: scripts e artefatos de instalação/atualização Windows, além de componentes de teste e recuperação.
- `tests/` e `benchmarks/`: testes e medição; a presença de arquivos não comprova aprovação de toda a suíte.
- `assets/`: identidade visual e ícones.

## Arquitetura

```text
Cliente MCP (ChatGPT)
    │ MCP Streamable HTTP / túnel seguro
    ▼
Servidor MCP autoral (loopback 127.0.0.1:8765/mcp)
    │ CBMCP/1, autenticação, controle de chamadas
    ▼
Adapter local (loopback 127.0.0.1:8766)
    ▼
Runtime CodeBridge
    ├─ terminal PowerShell 5.1
    ├─ terminal CMD
    ├─ terminal SSH (dependente de conexão)
    ├─ ledger de execuções e saída
    └─ serviços de leitura RAG
          ├─ SQLite/FTS5
          ├─ Qdrant local
          └─ Jina embeddings (texto e código)
```

Os serviços locais usam as portas indicadas na configuração atual; não são endereços para publicação direta na internet. O túnel é o transporte externo, não a autoridade de execução.

## Estado observado

Na auditoria desta documentação, o handshake MCP retornou `READY`, aplicativo `CodeBridge 2.0 - MCP Bridge`, versão `2.0.11-prealpha`. PowerShell e CMD estavam online; SSH configurado porém offline. Esses estados mudam com processos, conexão e disponibilidade de rede.

O índice RAG informado estava `READY`, com 211 documentos e 8.774 chunks, geração `v1_delta_1ae1d01ea84f4e`, indexada em 2026-10-09. São dados observados da instalação, **não constantes do software**.

## Contratos de uso

- Executar comandos via ferramentas MCP oficiais, respeitando as permissões do usuário Windows.
- Consultar o estado antes de assumir que SSH ou outro terminal está online.
- Associar a execução ao `execution_id`; nunca iniciar novamente um comando apenas porque a resposta ainda está `RUNNING`.
- O RAG lê o índice publicado. Planejamento de fontes não equivale a gravação autorizada.
- O aplicativo instalado pode estar em versão diferente do código da branch até ocorrer atualização/reinício.
- Para detalhes: [MCP_TOOLS_CURRENT.md](MCP_TOOLS_CURRENT.md), [EXECUTION_RUNTIME_CURRENT.md](EXECUTION_RUNTIME_CURRENT.md), [RAG_CURRENT.md](RAG_CURRENT.md) e [DESKTOP_DEPLOYMENT_CURRENT.md](DESKTOP_DEPLOYMENT_CURRENT.md).

## Fonte de verdade

Comportamento executável: código-fonte da revisão Git ativa. Disponibilidade: handshake/status da instalação em execução. Este documento descreve capacidade confirmada ou limites explícitos; não atribui certificação de produção a recursos experimentais.
