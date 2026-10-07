# RAG-003-B — Chunking de TXT e logs

Data: 2026-10-07  
Projeto: CodeBridge 2.0 — MCP Bridge  
Branch: `rag-003-text-chunking`

## Objetivo

Implementar chunking determinístico para TXT e logs

O handoff exige separar por

- seção
- execução
- erro
- evento
- limite controlado

Nenhum overlap é aplicado neste subpasso

## Prioridade de fronteiras

A ordem usada pelo parser é

```text
SECTION
EXECUTION
ERROR
EVENT
BLOCK
```

Quando uma linha abre uma nova fronteira semântica o bloco anterior é fechado e um novo chunk começa naquela linha

Conteúdo sem marcador explícito permanece como `BLOCK`

## Seção

São aceitos padrões como

```text
=== AUTH ===
--- NETWORK ---
[SECTION] Runtime
```

O título detectado fica em `marker`

## Execução

São reconhecidos padrões como

```text
execution_id=exec_001
execution_id: exec_001
execution exec_001
[EXECUTION] exec_001
```

O identificador detectado fica em `marker`

Isso é apenas segmentação textual

O ledger continua sendo a fonte oficial da execução

## Erro

Marcadores iniciais reconhecidos incluem

```text
ERROR
FATAL
FAILED
FAILURE
TRACEBACK
EXCEPTION
```

Também é aceito prefixo entre colchetes antes do nível de erro

Exemplo

```text
[2026-10-07T00:14:33Z] ERROR transport failed
```

Esse caso é classificado como `ERROR` e não como evento genérico

## Evento

São reconhecidos

```text
EVENT: sync-complete
[EVENT] sync-complete
```

E linhas iniciadas por timestamp ISO como

```text
2026-10-07T00:14:33Z INFO ready
2026-10-07 00:14:33 INFO ready
[2026-10-07T00:14:33Z] INFO ready
```

O texto após o timestamp quando presente fica em `marker`

## Limite controlado

A API recebe

```text
max_lines
```

Valor padrão

```text
80
```

Quando um bloco ultrapassaria esse limite ele é dividido exatamente por linhas

Exemplo com `max_lines=3`

```text
1  one
2  two
3  three
4  four
5  five
6  six
7  seven
```

produz

```text
chunk 0 linhas 1-3 continuation=false
chunk 1 linhas 4-6 continuation=true
chunk 2 linha 7 continuation=true
```

Nenhuma linha é repetida

Portanto o limite controlado não implementa overlap antecipadamente

## Nova fronteira após continuação

Se um chunk foi dividido pelo limite e a linha seguinte abre uma nova seção execução erro ou evento a nova unidade começa com

```text
continuation=false
```

Assim continuação significa apenas continuação forçada do mesmo bloco semântico por limite de tamanho

## Contrato produzido

Criado

`TextLogChunkDraft`

Campos

```text
ordinal
content
kind
line_start
line_end
continuation
marker
```

Tipos

```text
SECTION
EXECUTION
ERROR
EVENT
BLOCK
```

As linhas são coordenadas determinísticas do parser

A proveniência completa com path SHA-256 data source_type e project_id continua reservada ao RAG-003-D

## API

Criado

`rag/chunking/text_log.py`

API pública

```text
TextLogChunkKind
TextLogChunkDraft
chunk_text_log
```

`rag/chunking/__init__.py` foi atualizado para exportar os chunkers Markdown e TXT/log

## Corpus de teste

Criado

`tests/test_rag_text_log_chunking.py`

Coberturas

- bloco genérico
- seção
- execução
- erro
- evento
- timestamp com timezone
- timestamp sem timezone
- erro com timestamp entre colchetes
- prioridade de erro sobre evento
- limite controlado
- continuation
- ausência de overlap
- line ranges determinísticos
- trim apenas nas bordas
- conteúdo interno preservado
- determinismo
- entradas inválidas

## Efeitos colaterais

O chunker não

- lê filesystem
- escreve arquivos
- abre SQLite
- cria FTS5
- gera embeddings
- carrega Jina
- executa shell
- altera executor MCP

## Critério de aceitação do RAG-003-B

RAG-003-B está concluído quando

- seção cria fronteira determinística
- execução cria fronteira determinística
- erro cria fronteira determinística
- evento cria fronteira determinística
- conteúdo sem marcador continua preservado
- blocos grandes obedecem `max_lines`
- divisão controlada não duplica linhas
- nova fronteira zera `continuation`
- testes determinísticos passam
- overlap continua reservado ao RAG-003-C
- nenhuma fase posterior foi antecipada
