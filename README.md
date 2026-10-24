# CodeBridge 2.0 — MCP Bridge

CodeBridge é um aplicativo Windows que oferece **execução de comandos e consulta ao conhecimento local por ferramentas MCP**. Ele integra PowerShell 5.1, CMD, SSH configurável e uma camada RAG de recuperação lexical e semântica.

## Componentes

- `app_rewrite/`: interface PySide6, terminais, runtime, telemetria, configuração e gerenciadores locais.
- `author_mcp/`: servidor MCP autoral, protocolo, adapter, ferramentas e checkpoints.
- `rag/`: fontes, modelos Jina, chunking, SQLite FTS5, Qdrant, ranking e controle de gerações.
- `installer/`: instalação Windows NSIS, componentes de preparação, atualização e recuperação.
- `tests/` e `benchmarks/`: verificações e avaliação do comportamento.

## Fluxo

```text
Cliente MCP autorizado -> túnel seguro -> servidor MCP
    -> adapter local autenticado -> runtime CodeBridge
    -> terminais / ledger / RAG local
```

O runtime real controla as sessões e o estado das execuções. Uma resposta `RUNNING` deve ser acompanhada pelo `execution_id`, sem reenviar o comando. O RAG localiza contexto, mas não substitui os arquivos reais ou o Git como fonte de verdade.

## Principais ferramentas MCP

`codebridge_status`, `codebridge_capabilities`, `codebridge_read_batch`, `codebridge_prepare`, `codebridge_execute_prepared`, `codebridge_discard`, `codebridge_exec`, `codebridge_wait`, `codebridge_stop`, `codebridge_rag_status`, `codebridge_search_context`, `codebridge_get_context`, `codebridge_rag_index`, diagnósticos RAG e checkpoints de sessão.

**Estado de liberação:** a leitura de índices publicados e os terminais locais são implementados. SSH depende da conexão. A publicação incremental de novas fontes RAG e a atualização transacional da instalação ativa exigem validações e gates próprios; sua existência no código não significa aprovação para produção.

## Documentação técnica

A referência oficial é [docs/INDEX.md](docs/INDEX.md), com exatamente 12 documentos temáticos: arquitetura, MCP, executor, RAG, RAG interno, desktop, segurança, armazenamento, instalação, configuração e recuperação.

## Instalador

```powershell
.\installer\build_installer.ps1 -InstallNSIS
```

O comando prepara o instalador NSIS; não constitui autorização para implantar uma atualização sobre o aplicativo em uso.

## Repositório

Branch principal: `rag-017-optimized-inference-after-candidate`. O comportamento de cada revisão deve ser confirmado em seus módulos de código e testes, e a disponibilidade operacional pelo status do MCP.