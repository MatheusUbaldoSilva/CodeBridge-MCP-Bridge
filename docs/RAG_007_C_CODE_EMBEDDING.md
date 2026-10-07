# RAG-007-C — Embedding de código

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-007-jina-code`

## Objetivo

Indexar o corpus de código em um contrato de embedding logicamente separado do corpus textual.

## Dimensão efetiva

RAG-007-B provou com o artefato Q8_0 real e llama.cpp build 10819:

```text
DIM=1536
NORM=1.000000025
```

RAG-007-C congela portanto:

```text
CODE_EMBEDDING_DIMENSION=1536
```

A nota upstream de 896 dimensões permanece documentada como divergência histórica/ambiental; o contrato local usa a dimensão efetivamente observada e validada.

## Corpus

Somente:

`SourceType.CODE`

Documentação, audit, log, Git e execution não entram neste corpus.

## Roles

- QUERY
- PASSAGE

Cada vetor também carrega a tarefa explícita.

## Tarefas de corpus de código

Para chunks de código indexáveis:

- NL2CODE
- CODE2CODE

Ambas usam o passage prefix oficial:

`Candidate code snippet:\n`

Tarefas como CODE2NL e CODE2COMPLETION possuem semântica de passage diferente e não são aceitas pelo método de indexação do corpus de código nesta fase.

## Contrato numérico

```text
dimension=1536
norm_target=1.0
norm_tolerance=1e-3
repeatability_min_cosine=0.9999
batch_size=1
```

## Proveniência

`embed_code_chunks` preserva exatamente:

- chunk_id
- document_id
- project_id
- path
- symbol
- line_start
- line_end
- git_branch
- git_commit
- sha256
- source_id

O modelo nunca substitui a fonte real.

## Fronteira

RAG-007-C gera embeddings.

Não implementa:

- ranking;
- busca vetorial;
- NL → code retrieval;
- code → code retrieval;
- vector store;
- CPU benchmark.

Essas responsabilidades permanecem nos marcos seguintes.

## Implementação

Criado:

- `rag/models/code_embedding.py`
- `tests/test_rag_code_embedding.py`

Atualizado:

- `rag/models/__init__.py`

## Critério de aceitação

- dimensão 1536 congelada;
- SourceType.CODE exclusivo;
- prefixes por tarefa testados;
- provenance preservada;
- norma validada;
- repetibilidade validada com modelo real;
- chunks estruturais reais geram embeddings;
- suite RAG passa;
- diff check passa.


## Smoke real do cliente de embedding de código

O `CodeEmbeddingClient` foi executado contra o Q8_0 real já instalado.

Ambiente

```text
device=CUDA0
model=jina-code-embeddings-1.5b-Q8_0.gguf
ctx-size=8192
ubatch-size=8192
pooling=last
```

Foi embutido duas vezes o mesmo passage NL2CODE:

```cpp
bool CHARACTER::MoveItem(TItemPos src, TItemPos dst) {
    return CanMoveItem(src, dst);
}
```

Resultado

```text
DEVICE=CUDA0
PID=8876
DIM=1536
NORM=0.999999955
REPEAT_COS=0.999959919
DETERMINISTIC=True
```

A tolerância pública de repetibilidade

`cosine >= 0.9999`

foi satisfeita no backend GPU real.

## Corpus de código real do smoke

Foram usados dois chunks `SourceType.CODE`.

Chunk 1

```text
path=game/src/char_item.cpp
symbol=CHARACTER::MoveItem
lines=120-120
dimension=1536
norm=1.000000052
```

Chunk 2

```text
path=app/runtime.py
symbol=codebridge_wait
lines=80-81
dimension=1536
norm=1.000000008
```

O resultado retornou:

```text
COUNT=2
P0=game/src/char_item.cpp|CHARACTER::MoveItem|120-120
P1=app/runtime.py|codebridge_wait|80-81
DIMS=1536,1536
NORMS=1.000000052,1.000000008
UNLOAD=UNLOADED
```

Assim, embedding não removeu nem reinterpretou provenance.

## Observação sobre a dimensão

A dimensão 1536 deixou de ser somente uma observação isolada do RAG-007-B.

Ela foi novamente provada pelo cliente formal do RAG-007-C, incluindo múltiplos chunks.

Portanto o contrato local de embedding de código fica congelado em 1536 dimensões para este artefato e backend.

## Validação final

Testes específicos do RAG-007-C

```text
Ran 10 tests
OK
```

Suíte RAG completa

```text
Ran 360 tests
OK
```

Git whitespace audit

```text
git diff --check 26dff7100624a4f63d5aded442c5590251a6e294..HEAD
exit_code = 0
```

Worktree

```text
## HEAD (no branch)
```

sem alterações locais.

## Estado final do RAG-007-C

- corpus CODE logicamente separado;
- dimensão 1536 congelada;
- query e passage roles separados;
- task explícita em todo vetor;
- NL2CODE e CODE2CODE aceitos para corpus de código;
- prefixes oficiais testados;
- batch 1 congelado;
- norma unitária validada;
- repetibilidade real validada;
- provenance exata preservada;
- modelo descarregado ao final;
- 360 testes RAG passaram;
- diff check passou.

RAG-007-C está pronto para fechamento.
