# RAG-009-D — IDs determinísticos e reindexação idempotente

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-009-vector-index`

## Objetivo

Garantir que o mesmo chunk não crie novos pontos vetoriais duplicados a cada indexação

Requisito do handoff

`Mesmo chunk não pode criar duplicatas a cada indexação`

Fechamento do RAG-009 exige teste real de reindexação idempotente

## Política de identidade

Foram congelados três níveis

### Documento

`deterministic_document_id()`

Entrada

- project namespace
- source_type
- path relativo canônico

Saída

```text
doc:<sha256>
```

O conteúdo do arquivo não entra no document_id

Assim a identidade do documento permanece estável quando o arquivo é editado no mesmo caminho

### Chunk

`deterministic_chunk_id()`

Entrada

- document_id
- ordinal
- SHA-256 do conteúdo do chunk

Saída

```text
chunk:<sha256>
```

Mesmo documento mesmo ordinal e mesmo conteúdo produzem exatamente o mesmo chunk_id

Mudança de conteúdo ou ordinal produz novo chunk_id

A remoção de chunks antigos após alteração pertence ao fluxo incremental posterior do RAG-012

### Ponto vetorial

`deterministic_vector_point_id()`

Entrada

- project namespace
- collection text ou code
- chunk_id

Saída

UUID v5 determinístico

A namespace UUID é derivada de

`https://codebridge.local/rag/vector-id/v1`

Consequências

- mesmo chunk no mesmo projeto e coleção gera o mesmo point ID
- mesmo chunk em outro projeto gera outro point ID
- mesmo chunk em text e code gera IDs diferentes
- o ID é aceito nativamente pelo Qdrant

## Upsert idempotente

`upsert_vector_chunk()`

faz validação de

- coleção
- dimensão do vetor
- namespace
- chunk_id
- conflito de payload

Depois usa o point ID determinístico no upsert Qdrant

Repetir o upsert do mesmo chunk atualiza o mesmo ponto em vez de criar outro

## Prova real — text

Foi usado um chunk de documentação no namespace

`codebridge`

O mesmo chunk foi enviado duas vezes ao Qdrant Local com payload de revisão diferente

Resultado

```text
point_id da primeira indexação == point_id da segunda indexação
quantidade de pontos no namespace = 1
revision final = 2
```

Isso prova que a segunda indexação atualiza o ponto existente

## Prova real — code

Foi usado um chunk de código no namespace

`new-world-pvp`

O mesmo chunk foi enviado três vezes

Resultado

```text
quantidade de pontos no namespace = 1
```

Sem duplicação

## Path canônico

Document IDs tratam

```text
rag\index\vector_ids.py
```

e

```text
rag/index/vector_ids.py
```

como o mesmo caminho lógico

Paths absolutos ou com `..` são rejeitados

Isso evita identidade dependente da máquina local

## Dimensões

Antes do upsert

`text` exige `TEXT_EMBEDDING_DIMENSION`

`code` exige `CODE_EMBEDDING_DIMENSION`

Vetor com dimensão errada falha antes de chegar ao Qdrant

## Relação com provenance

O helper histórico de provenance continua aceitando IDs fornecidos pelo chamador para manter compatibilidade

A documentação interna foi atualizada para registrar que a política determinística oficial agora está congelada em

`rag.index.vector_ids`

## Arquivos

Criado

`rag/index/vector_ids.py`

Atualizado

`rag/index/__init__.py`

Atualizado

`rag/chunking/provenance.py`

Criado

`tests/test_rag_vector_ids.py`

Criado

`docs/RAG_009_D_DETERMINISTIC_IDS.md`

## Fronteiras

RAG-009-D não implementa limpeza de chunks órfãos após mudança de arquivo

Não decide se arquivo precisa ser reindexado

Não implementa stale detection

Esses comportamentos pertencem aos marcos posteriores de indexação incremental e Git

RAG-009-D prova somente identidade determinística e reindexação idempotente do mesmo chunk

## Critério de aceitação

RAG-009-D está concluído quando

- document_id é determinístico
- chunk_id é determinístico
- point ID é determinístico
- namespace participa da identidade
- coleção participa da identidade
- mesmo chunk reindexado em text não duplica
- mesmo chunk reindexado em code não duplica
- payload pode ser atualizado no mesmo ponto
- dimensão inválida é rejeitada
- testes específicos passam
- suíte RAG passa
- git diff check passa

Com isso RAG-009-A B C D fica pronto para closeout formal
