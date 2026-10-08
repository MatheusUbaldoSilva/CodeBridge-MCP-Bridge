# RAG-015 — Closeout de segurança

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-015-security`

## Estado

`RAG-015 ✅ FECHADO`

O marco de segurança foi concluído com todas as subfases A até E e com suíte negativa consolidada

O objetivo foi provar limites de segurança do RAG antes de qualquer declaração de produção

## Base

RAG-015 parte do fechamento do benchmark

`e969fb6 docs(rag-014): close benchmark milestone`

O benchmark anterior manteve

`PRODUCTION READINESS = BLOCKED`

RAG-015 não altera artificialmente essa decisão

## RAG-015-A — Secrets

Commit

`35b1940 feat(rag-015-a): block sensitive content from indexing`

Resultado

Duas camadas de proteção

```text
path denylist
↓
content secret detection
↓
allowlist
↓
index candidate
```

Detecção de alta confiança cobre

- private keys
- OpenAI keys
- GitHub tokens
- AWS access key ids
- Google API keys
- Slack tokens
- assignments explícitos de secrets

Findings registram somente

- tipo
- linha
- fingerprint

O raw secret não é devolvido

Placeholders runtime references hashes e IDs comuns não são marcados como segredo

`RagIndexPlan.sensitive_count` torna a negação auditável

## RAG-015-B — Escopo

Commit

`493ad47 test(rag-015-b): prove cross-project scope isolation`

Foi criado cenário adversarial com

```text
codebridge
drones
```

usando

- mesmo SQLite
- mesmo FTS5
- mesmas collections Qdrant
- conteúdo equivalente
- vetores equivalentes

Foi provado que

- lexical respeita project_id
- text vector respeita namespace
- code vector respeita namespace
- HYBRID respeita namespace
- get_context não aceita chunk_id do outro projeto

Nenhum ajuste de produção foi necessário porque as barreiras anteriores já estavam corretas

## RAG-015-C — Path traversal

Commit

`dd1a818 test(rag-015-c): prove path traversal isolation`

Vetores negativos testados

```text
../outside.py
docs/../../outside.md
..\outside.py
docs\..\..\outside.md
path absoluto externo
```

Foram provadas barreiras em

- denylist
- index planning
- staleness
- get_context
- Git provenance
- Git worktree

Um path normalizado que continua dentro da raiz permanece permitido

Nenhum ajuste adicional de produção foi necessário

## RAG-015-D — Origem de chunks

Commit

`47e9944 feat(rag-015-d): require chunk origin provenance`

Criado

`ChunkOriginRecord`

e

`require_chunk_origin()`

Origem mínima obrigatória no caminho oficial

```text
chunk_id
document_id
project_id
source_type
path
line_start
line_end
sha256
indexed_at
source_id opcional
```

`attach_source_provenance()`

agora valida cada chunk com `require_chunk_origin()` antes de devolvê-lo

Foi provado round-trip

```text
source
↓
Chunk
↓
SQLite
↓
FTS5
↓
SearchResult
```

preservando proveniência

## RAG-015-E — Exclusão

Commit

`48b3e96 feat(rag-015-e): delete project index without source mutation`

Criado

`delete_project_index()`

A exclusão é namespace-scoped

Remove somente

- SQLite documents do projeto
- chunks e symbols por cascade
- rag_index_state do projeto
- text vector points do namespace
- code vector points do namespace
- manifest entries do projeto

Não dropa collections compartilhadas

Não recebe project_root nem source path

Os arquivos originais foram monitorados por bytes e mtime durante os testes e permaneceram idênticos

A operação é idempotente

## Suíte negativa consolidada

Executados em conjunto

```text
tests.test_rag_secret_detection
tests.test_rag_015_scope_security
tests.test_rag_015_path_traversal
tests.test_rag_015_chunk_origin
tests.test_rag_015_project_deletion
```

Resultado observado

```text
Ran 34 tests in 2.722s
OK
```

Esses testes incluem falhas intencionais e tentativas de bypass

## Suíte RAG completa

Após RAG-015-E

```text
Ran 675 tests in 18.394s
OK
```

## Arquitetura de segurança consolidada

```text
source discovery
↓
path denylist
↓
project root boundary
↓
source allowlist
↓
secret content scan
↓
chunk provenance validation
↓
project namespace
↓
SQLite / FTS5
↓
Qdrant namespace filter
↓
search
↓
get_context authorization
↓
staleness / path revalidation
```

Para exclusão

```text
project namespace
↓
derived SQLite rows
derived vector points
manifest entries
↓
source files untouched
```

## Invariantes congelados

1 um filename inocente não é suficiente para autorizar conteúdo sensível

2 conhecer chunk_id de outro projeto não concede acesso

3 project A nunca pode receber project B quando o scope é explícito

4 path traversal é recusado antes de filesystem ou Git escapar da raiz

5 um chunk do caminho oficial precisa possuir origem mínima rastreável

6 excluir um projeto do RAG não significa excluir o projeto do disco

7 collections vetoriais compartilhadas não são dropadas para remover um namespace

8 falha de segurança não é convertida em fallback permissivo

## Commits do marco

```text
35b1940 RAG-015-A secrets
493ad47 RAG-015-B scope
dd1a818 RAG-015-C path traversal
47e9944 RAG-015-D chunk origin
48b3e96 RAG-015-E safe project deletion
```

## Critério de fechamento

RAG-015 pode ser fechado porque

- secrets são bloqueados por path e conteúdo
- scope cross-project foi testado negativamente
- traversal foi testado negativamente
- origem de chunks foi tornada verificável
- remoção de projeto/index não toca fontes
- outro projeto permanece intacto durante purge
- operação de purge é idempotente
- 34 testes negativos consolidados passaram
- 675 testes RAG passaram
- cada subfase possui commit próprio
- branch está sincronizada com origin antes do closeout

## Próximo marco

O próximo marco oficial deve ser lido do handoff antes de abrir nova implementação

Nenhum passo posterior deve reinterpretar o gate de benchmark do RAG-014 como aprovado

A produção continua condicionada aos critérios objetivos já congelados
