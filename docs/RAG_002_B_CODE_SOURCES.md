# RAG-002-B — Inventário de fontes de código e configuração

Data: 2026-10-06  
Projeto: CodeBridge 2.0 — MCP Bridge  
Branch: `rag-002-source-inventory`

## Objetivo

Congelar a allowlist inicial de extensões de código e configuração que poderão ser tratadas pela camada RAG

Este subpasso apenas classifica paths

Não executa parser chunking indexação embedding ou inferência

## Allowlist exigida pelo handoff

### Código nativo

```text
.c
.cc
.cpp
.h
.hpp
```

### Python e shell

```text
.py
.ps1
.bat
.cmd
.sh
```

### Web e JavaScript TypeScript

```text
.js
.ts
```

### Configuração estruturada

```text
.json
.yaml
.yml
.toml
```

## Extensões adicionais aprovadas para o CodeBridge 2.0

O repositório atual usa fontes estruturadas que também precisam ser encontráveis pelo RAG

```text
.html
.css
.nsi
.nsh
```

Motivo

- HTML e CSS fazem parte da interface web local
- NSI e NSH fazem parte do instalador NSIS

Essas extensões entram como fontes técnicas aprovadas do CodeBridge 2.0

## Manifesto especial aprovado

```text
requirements.txt
```

A aprovação é pelo nome exato e não pela extensão `.txt`

Assim logs TXT documentos TXT e outputs arbitrários não passam a ser tratados como código

## Classificação

Implementada em

`rag/sources/code_inventory.py`

Categorias

```text
CODE
WEB
CONFIG
INSTALLER
DEPENDENCY_MANIFEST
```

## Snapshot atual do branch

Arquivos totais auditados

```text
138
```

Fontes de código e configuração elegíveis pelas regras do RAG-002-B

```text
115
```

Distribuição atual

```text
.py   = 101
.ps1  = 2
.js   = 4
.json = 2
.html = 1
.css  = 1
.nsi  = 1
.nsh  = 1
requirements.txt = 2
```

As demais extensões aprovadas ainda não existem no snapshot atual mas já ficam permitidas pelo contrato para projetos que as utilizarem

## Exemplos reais incluídos

```text
app_rewrite/runtime.py
author_mcp/mcp_server.py
installer/bootstrap.ps1
browser_extension/codebridge_chatgpt_timer/background.js
browser_extension/codebridge_chatgpt_timer/manifest.json
app_rewrite/web_terminal/terminal.html
app_rewrite/web_terminal/static/xterm.css
installer/CodeBridge.nsi
installer/version.nsh
requirements.txt
author_mcp/requirements.txt
```

## Exclusões observadas neste subpasso

Não são fontes de código do RAG-002-B

```text
.md
.exe
.png
.ico
.mp3
.sha256
.gitignore
TXT genérico
```

Documentos Markdown continuam pertencendo ao inventário documental do RAG-002-A

Binários imagens áudio e checksums não entram nesta allowlist

Arquivos sensíveis como `.env` chaves privadas e tokens não são aprovados aqui e serão reforçados pela denylist do RAG-002-E

## Invariantes

- extensão não aprovada retorna nenhuma classificação
- `.txt` não é permitido globalmente
- `requirements.txt` é permitido somente pelo nome exato
- paths Windows são normalizados
- nenhuma leitura de conteúdo acontece nesta fase
- nenhum modelo é carregado
- nenhum índice é criado
- nenhuma mudança no executor é necessária

## Critério de aceitação do RAG-002-B

RAG-002-B está concluído quando

- todas as extensões definidas no handoff estão permitidas
- as extensões adicionais reais do CodeBridge estão justificadas
- manifests especiais não ampliam `.txt` de forma insegura
- binários e documentação não são classificados como código
- o inventário atual está documentado
- os testes determinísticos cobrem allowlist e exclusões
