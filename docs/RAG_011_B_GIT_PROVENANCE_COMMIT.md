# RAG-011-B — Commit de proveniência por arquivo ou trecho

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-011-git-metadata`

## Objetivo

Associar ao chunk o último commit Git realmente relevante ao arquivo ou trecho quando essa informação puder ser determinada

Requisito do handoff

`Quando possível associar último commit relevante ao arquivo/trecho`

## Separação entre HEAD e proveniência

RAG-011-A já captura o estado global do repositório

```text
git_branch
git_commit = HEAD capturado no momento da indexação
```

RAG-011-B não sobrescreve esse valor

Foi adicionado ao contrato `SourceMetadata`

`git_provenance_commit`

Assim ficam separados

```text
git_commit
→ HEAD do repositório no momento da captura

git_provenance_commit
→ commit mais recente relevante ao arquivo ou trecho
```

Isso evita confundir estado global do repositório com origem histórica do conteúdo

## Captura por arquivo

`capture_git_file_provenance()`

sem intervalo de linhas executa leitura equivalente a

```text
git log -1 --format=%H -- <path>
```

Resultado

`GitFileProvenance(scope="FILE")`

contendo

- repository_root
- path relativo canônico
- commit
- scope

## Captura por trecho

Quando `line_start` e `line_end` são fornecidos primeiro é tentada leitura equivalente a

```text
git log -1 --format=%H -L <start>,<end>:<path>
```

Se o Git consegue resolver o histórico do trecho

```text
scope=LINE_RANGE
line_start=<start>
line_end=<end>
commit=<commit relevante mais recente>
```

## Fallback

Nem todo arquivo ou situação permite `git log -L`

Quando a resolução de linha não é possível a captura faz fallback para o último commit do arquivo

```text
LINE_RANGE não resolvido
↓
FILE provenance
```

Assim a granularidade mais específica é usada quando disponível sem transformar uma limitação do Git em perda total da proveniência

## Arquivo não rastreado

Arquivo untracked ainda não possui commit de proveniência

Resultado

`None`

Nenhum SHA é inventado

RAG-011-C tratará separadamente o estado de arquivos modificados e não rastreados no working tree

## Path seguro

O path é normalizado para formato relativo ao root Git

Exemplo

`src/main.py`

Separadores Windows e POSIX convergem para o mesmo caminho lógico

Path absoluto é permitido somente quando está dentro do repository root

Path fora do repositório é rejeitado

Uso de `..` para escapar do root também é rejeitado

## Anexação ao metadata

`attach_git_provenance_to_metadata()`

preenche somente

`git_provenance_commit`

e preserva

- git_branch
- git_commit HEAD
- path
- SHA do conteúdo
- indexed_at
- demais metadados

O objeto original continua imutável

## Anexação ao chunk

`attach_git_provenance_to_chunk()`

quando a proveniência é de linha valida que o intervalo do chunk corresponde ao intervalo usado para consultar o Git

Se houver conflito de path ou intervalo a operação falha explicitamente

Isso impede anexar commit histórico de outro trecho por engano

## Prova real

Os testes criam repositório Git temporário real com dois commits

Primeiro commit

```text
alpha = 1
beta = 2
gamma = 3
delta = 4
```

Segundo commit altera somente

```text
beta = 20
```

Resultados provados

- provenance do arquivo inteiro aponta para o segundo commit
- provenance da linha 2 aponta para o segundo commit
- provenance da linha 4 aponta para o primeiro commit
- path absoluto interno é normalizado
- arquivo untracked retorna None
- path externo é rejeitado
- intervalo inválido é rejeitado
- captura fora de repositório retorna GitProvenanceError
- HEAD existente é preservado ao anexar provenance
- chunk original permanece imutável

## Contrato atualizado

`SourceMetadata` agora contém

```text
git_branch
git_commit
git_provenance_commit
```

Semântica

```text
git_branch             branch capturada
git_commit             HEAD capturado
git_provenance_commit  último commit relevante ao arquivo ou trecho
```

## Helper de chunking

`attach_source_provenance()`

passou a aceitar opcionalmente

`git_provenance_commit`

para que pipelines que já tenham resolvido a proveniência possam construir chunks com o campo preservado

## Arquivos

Criado

`rag/sources/git_provenance.py`

Atualizado

`rag/sources/__init__.py`

Atualizado

`rag/contracts.py`

Atualizado

`rag/chunking/provenance.py`

Criado

`tests/test_rag_git_file_provenance.py`

Criado

`docs/RAG_011_B_GIT_PROVENANCE_COMMIT.md`

## Fronteiras

RAG-011-B não decide se o working tree está modificado

Isso pertence ao RAG-011-C

RAG-011-B não compara SHA indexado com arquivo atual

Isso pertence ao RAG-011-D

RAG-011-B não faz indexação incremental

Isso pertence ao RAG-012

## Critério de aceitação

RAG-011-B está concluído quando

- último commit do arquivo pode ser capturado
- último commit do trecho pode ser capturado quando Git permite
- fallback para arquivo existe
- untracked não recebe commit inventado
- HEAD e provenance permanecem separados
- provenance é anexável ao metadata e ao chunk
- conflito de path ou intervalo é rejeitado
- testes específicos passam
- suíte RAG passa
- git diff check passa
