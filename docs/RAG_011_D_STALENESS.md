# RAG-011-D — Staleness por SHA do arquivo atual

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-011-git-metadata`

## Objetivo

Marcar um resultado como potencialmente stale quando o conteúdo indexado não corresponde mais ao arquivo atual

Requisito do handoff

`Marcar resultado como potencialmente stale quando SHA do índice divergir do arquivo atual`

Critério de fechamento do RAG-011

`teste de arquivo alterado após indexação`

## Fonte da comparação

O chunk já possui em `SourceMetadata`

`sha256`

Esse SHA representa o conteúdo fonte no momento da indexação

RAG-011-D lê o arquivo atual e calcula novamente

```text
SHA-256 UTF-8 do arquivo atual
```

A comparação é feita entre

```text
indexed_sha256
current_sha256
```

## Estados

`StalenessStatus`

possui

```text
FRESH
STALE
UNKNOWN
```

### FRESH

```text
indexed_sha256 == current_sha256
```

reason

`SHA_MATCH`

### STALE

SHA atual diverge do SHA indexado

reason

`SHA_MISMATCH`

Arquivo indexado foi removido

reason

`FILE_MISSING`

Path deixou de representar arquivo normal

reason

`NOT_A_FILE`

### UNKNOWN

Não existe path no metadata

`PATH_UNAVAILABLE`

Não existe SHA indexado

`INDEXED_SHA_UNAVAILABLE`

Arquivo atual não pôde ser lido como fonte UTF-8

`READ_FAILED`

UNKNOWN não é transformado automaticamente em stale

Isso evita inventar divergência quando não existe evidência suficiente

## Resultado estruturado

`StalenessEvaluation`

contém

- status
- path
- indexed_sha256
- current_sha256
- reason

A propriedade

`stale`

é verdadeira somente para estado STALE

## Marcação do SearchResult

O contrato `SearchResult` já possuía

`stale: bool`

Criado

`mark_search_result_staleness()`

Fluxo

```text
SearchResult
+
StalenessEvaluation
↓
novo SearchResult
stale = evaluation.stale
```

O SearchResult original permanece imutável

## Teste obrigatório do handoff

Foi implementado explicitamente

`test_file_changed_after_indexing_is_stale`

Fluxo real do teste

```text
criar arquivo
↓
calcular SHA indexado
↓
construir SourceMetadata
↓
alterar arquivo depois da indexação
↓
recalcular SHA atual
↓
detectar SHA_MISMATCH
↓
status STALE
```

Isso cumpre o critério específico de fechamento do RAG-011

## Outros testes

Também são validados

- arquivo inalterado fica FRESH
- arquivo removido fica STALE
- ausência de path fica UNKNOWN
- ausência de SHA fica UNKNOWN
- SearchResult recebe stale=True
- avaliação FRESH pode limpar stale anterior
- tentativa de escapar do repository root é rejeitada

## Relação com RAG-011-C

RAG-011-C responde

`o working tree está modificado?`

RAG-011-D responde

`o conteúdo atual ainda é igual ao conteúdo que foi indexado?`

Essas perguntas não são equivalentes

Um arquivo pode estar marcado MODIFIED por Git mas a alteração pode não pertencer ao mesmo snapshot ou contexto esperado

O SHA é a prova direta de conteúdo para staleness

## Segurança do path

O arquivo é resolvido dentro do repository root fornecido

Path que escapa com `..` é rejeitado

Nenhum comando shell é executado nesta fase

## Arquivos

Criado

`rag/sources/staleness.py`

Atualizado

`rag/sources/__init__.py`

Criado

`tests/test_rag_source_staleness.py`

Criado

`docs/RAG_011_D_STALENESS.md`

## Fronteiras

RAG-011-D não reindexa automaticamente arquivo stale

RAG-011-D não remove chunks órfãos

RAG-011-D não mantém manifest incremental

Esses comportamentos pertencem ao RAG-012

## Critério de aceitação

RAG-011-D está concluído quando

- SHA indexado pode ser comparado ao arquivo atual
- SHA igual retorna FRESH
- SHA diferente retorna STALE
- arquivo removido retorna STALE
- ausência de evidência retorna UNKNOWN
- SearchResult pode receber stale=True
- teste de arquivo alterado após indexação passa
- suíte RAG passa
- git diff check passa

Com isso RAG-011-A B C D fica pronto para closeout formal
