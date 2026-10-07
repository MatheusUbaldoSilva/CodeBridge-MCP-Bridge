# RAG-003-D — Proveniência de chunks

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-003-text-chunking`

## Objetivo

Fechar a proveniência obrigatória dos chunks textuais produzidos no RAG 003

Cada chunk passa a manter

- path
- linhas
- SHA-256
- data
- source_type
- project_id

## Fonte verificada

A proveniência não é montada confiando somente no draft do chunk

`attach_source_provenance` recebe o texto fonte completo e antes de criar o `Chunk`

1 normaliza o path

2 calcula SHA-256 do texto fonte completo em UTF-8

3 verifica `line_start` e `line_end`

4 relê o intervalo declarado dentro do texto fonte

5 exige igualdade exata com `draft.content`

6 cria `SourceMetadata`

7 cria o `Chunk` imutável

Se conteúdo ou linhas divergirem a criação falha

## Path

O path salvo é relativo ao projeto

Paths Windows são normalizados

`docs\example.md` vira `docs/example.md`

Path absoluto path UNC e path traversal com `..` são rejeitados

## Linhas

`line_start` e `line_end` vêm dos chunkers determinísticos do RAG 003 A e RAG 003 B

As linhas são 1 based

A proveniência valida que o intervalo ainda corresponde exatamente ao texto fonte recebido

## SHA-256

O SHA-256 registrado é o hash do documento fonte inteiro

Não é o hash isolado de cada pedaço

Todos os chunks do mesmo snapshot de fonte compartilham o mesmo SHA-256

Isso permite detectar staleness posteriormente comparando a fonte real com o snapshot usado na criação dos chunks

## Data

O campo temporal do contrato atual é `indexed_at`

RAG 003 D congela `indexed_at` como a data de captura ou indexação da proveniência textual

Ele deve ser ISO 8601 com timezone

Exemplos válidos

`2026-10-07T03:14:00Z`

`2026-10-07T00:14:00-03:00`

## source_type

Usa diretamente `SourceType` definido no RAG 001 C

Exemplos nesta frente

- DOCUMENTATION
- LOG
- AUDIT
- EXECUTION

Nenhuma string arbitrária substitui o enum

## project_id

`project_id` é obrigatório e identifica o namespace lógico da fonte

Exemplo `codebridge`

## IDs

RAG 003 D não inventa política determinística de `document_id` ou `chunk_id`

Esses IDs são fornecidos pelo chamador

A política de IDs determinísticos continua reservada ao RAG 009 D

Assim o RAG 003 fecha proveniência sem antecipar o desenho do índice vetorial

## Git opcional

Quando disponível a proveniência também preserva

- git_branch
- git_commit
- source_id

Esses campos continuam opcionais porque nem toda fonte textual pertence a um commit Git

## Overlap

A proveniência é anexada ao chunk primário original

Texto duplicado pela view de overlap do RAG 003 C não altera

- SHA-256
- line_start
- line_end
- conteúdo primário do Chunk

A view de overlap mantém suas coordenadas separadas

Isso evita representar linhas duplicadas como se fossem parte original do chunk

## Implementação

Criado `rag/chunking/provenance.py`

API pública

- `source_sha256`
- `attach_source_provenance`

`rag/chunking/__init__.py` também passa a exportar essas APIs

## Testes

Criado `tests/test_rag_chunk_provenance.py`

O corpus cobre

- Markdown com proveniência completa
- TXT e log com linhas exatas
- SHA-256 do documento inteiro
- normalização de path Windows
- rejeição de conteúdo adulterado
- rejeição de faixa fora da fonte
- rejeição de path traversal
- rejeição de path absoluto Windows Linux e UNC
- ISO 8601 com timezone obrigatório
- quantidade de IDs
- IDs duplicados
- SourceType obrigatório
- preservação dos IDs fornecidos pelo chamador

## Efeitos colaterais

A camada de proveniência não

- lê filesystem
- grava arquivos locais
- abre SQLite
- cria FTS5
- gera embedding
- carrega Jina
- executa shell
- altera executor MCP

## Critério de aceitação do RAG 003 D

RAG 003 D está concluído quando

- cada Chunk criado possui project_id
- cada Chunk criado possui path
- cada Chunk criado possui line_start e line_end
- cada Chunk criado possui SHA-256 verificável
- cada Chunk criado possui indexed_at com timezone
- cada Chunk criado possui source_type
- conteúdo é validado contra a fonte real recebida
- política de IDs futuros não é antecipada
- corpus determinístico passa
