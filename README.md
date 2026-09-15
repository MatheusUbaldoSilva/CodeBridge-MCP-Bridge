# CodeBridge MCP Bridge

> CodeBridge 2.0 — MCP Bridge

Status: **Pre-alpha / arquitetura inicial**

CodeBridge MCP Bridge é a segunda geração do CodeBridge. Ele nasce como um projeto separado do CodeBridge 1.x — Browser Bridge para preservar a versão atual funcionando enquanto a integração MCP é construída do zero.

## Objetivo

Permitir que o ChatGPT opere PowerShell 5.1, CMD e SSH por meio do CodeBridge sem depender de extensão de navegador, automação do DOM, digitação simulada ou blocos `@CODEBRIDGE`.

Arquitetura alvo:

```text
ChatGPT
   ↓ MCP
Remote Desktop Commander
   ↓
CodeBridge 2.0
   ↓
Fila / políticas / aprovação
   ↓
PowerShell 5.1 | CMD | SSH
   ↓
Resultado estruturado
   ↑
MCP
   ↑
ChatGPT
```
## Princípio central

O Remote Desktop Commander é o canal de transporte, não a autoridade de execução.

As solicitações de automação entram no CodeBridge 2.0 e passam por política, fila, aprovação, execução, cancelamento, histórico e auditoria.

## O que deixa de existir no 2.0

- extensão Chrome obrigatória;
- leitura do DOM do ChatGPT;
- digitação simulada no compositor;
- protocolo textual legado do Browser Bridge;
- identificação por aba do navegador;
- entrega de resultados dependente da extensão.
## O que será preservado e evoluído

- sessões persistentes de PowerShell 5.1, CMD e SSH;
- fila e políticas locais;
- aprovação antes da execução;
- stop e cancelamento;
- histórico e resultados estruturados;
- monitoramento e reconexão SSH;
- telemetria e estado visual do runtime;
- execução sequencial e parada segura em falhas.

## API estrutural planejada

A nova integração não depende de blocos formatados. O protocolo interno será composto por operações explícitas como `status`, `run`, `cancel`, `stop`, `result` e `history`.

O objetivo é que o usuário possa pedir uma tarefa em linguagem natural e o ChatGPT acione essas operações por MCP sem precisar exibir o protocolo de transporte.
