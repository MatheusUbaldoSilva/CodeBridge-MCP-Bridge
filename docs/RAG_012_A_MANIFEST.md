# RAG-012-A — Manifest persistente de indexação

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-012-incremental-index`

## Objetivo

Persistir o estado mínimo necessário para indexação incremental

Requisito do handoff

- path
- size
- mtime
- SHA-256
- chunk ids
- versão do modelo

## Formato

Foi criado manifest JSON versionado

`MANIFEST_SCHEMA_VERSION = 1`

Nome padrão

`rag-index-manifest.json`

A persistência é explícita

Nenhum manifest é criado no import

## Entrada

`ManifestEntry`

persiste

```text
project_id
index_kind
path
size
mtime_ns
sha256
chunk_ids
model_version
```

Os seis campos obrigatórios do handoff estão presentes

`index_kind` foi adicionado para separar TEXT e CODE desde o início e permitir que RAG-012-E invalide somente o índice do modelo que mudou

## Espaços

`ManifestIndexKind`

```text
TEXT
CODE
```

A mesma path pode possuir uma entrada TEXT e outra CODE sem colisão

## Chave determinística

Cada entrada possui chave derivada de

```text
schema version
project namespace
index kind
path canônico
```

por SHA-256

Isso separa

- projetos
- espaços de embedding
- arquivos

## Path

Paths são relativos ao projeto e normalizados para separador POSIX

```text
.\docs\readme.md
docs/readme.md
```

produzem a mesma identidade

Paths absolutos e escapes com `..` são rejeitados

## Validação

size

inteiro maior ou igual a zero

mtime_ns

inteiro maior ou igual a zero

sha256

64 caracteres hexadecimais

chunk_ids

strings não vazias e únicas

model_version

string não vazia

## Operações

`IndexManifest.get()`

busca entrada por projeto espaço e path

`IndexManifest.upsert()`

substitui somente a entrada de mesma identidade lógica

`IndexManifest.remove()`

remove somente a entrada alvo

## Persistência

`save_index_manifest()`

serializa JSON determinístico com

- UTF-8
- chaves ordenadas
- entries ordenadas por chave
- schema_version explícita

A gravação usa arquivo temporário no mesmo diretório seguido de replace

Isso evita escrever diretamente sobre o arquivo final durante a serialização

`load_index_manifest()`

carrega e valida a versão e todas as entradas

Manifest inexistente retorna estado vazio

Manifest inválido gera `ManifestError`

## Provas

Os testes validam

- todos os campos obrigatórios
- path canônico
- chave determinística
- isolamento entre TEXT e CODE
- isolamento entre projetos
- upsert idempotente
- remoção seletiva
- manifest inexistente
- round trip em disco
- JSON determinístico
- schema_version
- versão incompatível rejeitada
- chave duplicada rejeitada
- campos inválidos rejeitados

## Arquivos

Criado

`rag/index/manifest.py`

Atualizado

`rag/index/__init__.py`

Criado

`tests/test_rag_index_manifest.py`

Criado

`docs/RAG_012_A_MANIFEST.md`

## Fronteiras

RAG-012-A apenas persiste o estado

RAG-012-B decidirá pular arquivo com SHA igual

RAG-012-C fará reprocessamento seletivo

RAG-012-D removerá chunks órfãos

RAG-012-E tratará mudança de versão do modelo

## Critério de aceitação

RAG-012-A está concluído quando

- manifest possui path
- size é persistido
- mtime é persistido
- SHA-256 é persistido
- chunk ids são persistidos
- versão do modelo é persistida
- TEXT e CODE ficam distinguíveis
- round trip em disco passa
- testes específicos passam
- suíte RAG passa
- git diff check passa
