# RAG-003-C — Overlap controlado

Data: 2026-10-07
Projeto: CodeBridge 2.0 — MCP Bridge
Branch: `rag-003-text-chunking`

## Objetivo

Definir overlap somente quando necessário e evitar duplicação excessiva de contexto

O overlap é aplicado depois do chunking sem mudar as fronteiras semânticas produzidas pelo Markdown ou pelo TXT/log

## Regra central

Overlap não é automático entre todos os chunks

A política padrão exige

1. não ser o primeiro chunk
2. `continuation=true`
3. faixa de linhas contígua ao chunk anterior
4. mesmo tipo semântico quando ambos possuem `kind`
5. mesmo marcador quando ambos possuem `marker`
6. overlap solicitado maior que zero

Se qualquer condição falhar o conteúdo permanece sem duplicação

## Quando overlap é necessário

No RAG-003-B um bloco TXT ou log pode ser dividido somente porque atingiu `max_lines`

A parte seguinte recebe

`continuation=true`

Esse é o caso padrão onde algumas linhas anteriores podem ajudar a preservar contexto

Exemplo

```text
chunk 0  linhas 1-8   continuation=false
chunk 1  linhas 9-16  continuation=true
```

O chunk 1 pode receber um pequeno sufixo do chunk 0

## Quando overlap não é aplicado

### Nova seção execução erro ou evento

Uma nova fronteira semântica zera `continuation`

Portanto não herda texto da unidade anterior

### Markdown

Os chunks Markdown já preservam hierarquia por `heading_path`

Por isso o RAG-003-C não duplica parágrafos Markdown por padrão

### Faixas não contíguas

Se

```text
previous.line_end + 1 != current.line_start
```

nenhum overlap é aplicado

### Tipo ou marcador diferente

Continuação inconsistente não é usada para justificar duplicação

## Limites de duplicação

Parâmetros padrão

```text
overlap_lines = 2
max_overlap_lines = 4
max_overlap_fraction = 0.25
```

O número efetivo é o menor entre

- linhas solicitadas
- teto absoluto
- teto proporcional ao tamanho primário do chunk atual
- quantidade de linhas disponíveis no chunk anterior

Para chunks muito pequenos é permitido no máximo uma linha mínima de contexto quando a continuação foi explicitamente marcada

## Representação

Criado

`ControlledOverlapChunk`

Campos

```text
source_ordinal
content
primary_content
primary_line_start
primary_line_end
overlap_line_start
overlap_line_end
overlap_lines
reason
```

`primary_content` continua sendo o conteúdo original do chunk

`content` é a visão usada para recuperação quando overlap for aplicado

Assim a camada não destrói a distinção entre conteúdo primário e texto duplicado

## Motivo

Motivo inicial congelado

```text
FORCED_CONTINUATION
```

Nenhum outro motivo de overlap foi aprovado neste subpasso

## Imutabilidade

Os chunks produzidos pelos chunkers anteriores não são modificados

`apply_controlled_overlap` cria novas views

Isso mantém o chunking semântico original auditável

## Implementação

Criado

`rag/chunking/overlap.py`

API pública

```text
OverlapReason
ControlledOverlapChunk
apply_controlled_overlap
```

`rag/chunking/__init__.py` foi atualizado

## Testes

Criado

`tests/test_rag_controlled_overlap.py`

O corpus cobre

- overlap em continuação forçada
- teto absoluto
- teto proporcional
- tail pequeno
- nova fronteira semântica sem overlap
- incompatibilidade de tipo ou marker
- linhas não contíguas
- Markdown sem overlap padrão
- overlap zero
- imutabilidade dos chunks fonte
- determinismo
- parâmetros inválidos

## Proveniência

Este subpasso preserva coordenadas primárias e coordenadas específicas do overlap

A proveniência completa com path SHA-256 data source_type e project_id continua reservada ao RAG-003-D

## Efeitos colaterais

A política de overlap não

- lê filesystem
- grava arquivos
- abre SQLite
- cria FTS5
- gera embeddings
- carrega Jina
- executa shell
- altera executor MCP

## Critério de aceitação do RAG-003-C

RAG-003-C está concluído quando

- overlap não é aplicado globalmente
- somente continuação forçada recebe overlap por padrão
- nova fronteira semântica não duplica contexto
- Markdown permanece sem duplicação padrão
- teto absoluto e proporcional limitam repetição
- chunks originais permanecem imutáveis
- testes determinísticos passam
- proveniência final continua reservada ao RAG-003-D
