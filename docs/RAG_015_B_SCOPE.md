# RAG-015-B — Escopo entre projetos

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-015-security`

## Objetivo

Provar negativamente que um projeto não recebe conteúdo de outro projeto quando o scope explícito está ativo

Requisito do handoff

`Projeto A não deve vazar resultados do projeto B quando scope explícito estiver ativo`

## Estratégia

Foi criado um teste de segurança com dois projetos armazenados no mesmo índice físico

```text
project A = codebridge
project B = drones
```

Os dois projetos recebem conteúdo deliberadamente igual

Isso evita um falso PASS causado por queries que só combinariam com um lado

Também recebem vetores deliberadamente idênticos

Assim se o filtro de namespace falhar o resultado do outro projeto necessariamente pode aparecer

## Storage compartilhado usado

O teste usa componentes reais

- SQLite real
- FTS5 real
- Qdrant Local real
- collection text compartilhada
- collection code compartilhada
- get_context real

Não são usados mocks para isolamento

## Corpus adversarial

Projeto A

```text
chunk-a-text
chunk-a-code
```

Projeto B

```text
chunk-b-text
chunk-b-code
```

Textos equivalentes e vetores iguais são usados entre A e B

A única barreira é o namespace do projeto

## Prova lexical

Query com

`project_id=codebridge`

executada em FTS5

Critério

- todo SearchResult precisa ter project_id codebridge
- chunk-b-text não pode aparecer
- chunk-b-code não pode aparecer

Resultado

`PASS`

## Prova vetorial e HYBRID

Foi executado

`collect_hybrid_query_candidates()`

com

- FTS5
- text vector
- code vector

para project A

Todos os três rankings são verificados

```text
lexical
text_vector
code_vector
```

Nenhum item de project B apareceu

A prova foi repetida na direção inversa

project B também não recebeu chunks de project A

## Prova de get_context

Um ataque simples é conhecido

o cliente conhece diretamente o chunk_id do outro projeto e tenta buscá-lo usando seu próprio scope

Teste

```text
project_id=codebridge
chunk_ids=[chunk-b-text]
```

Resultado esperado

`RagContextSourceMissingError`

Resultado observado

`PASS`

O mesmo serviço consegue recuperar normalmente

`chunk-a-text`

quando o project_id é codebridge

## Defesa em profundidade já existente

A arquitetura protege o scope em múltiplas camadas

### SQLite

SearchQuery carrega project_id e o caminho lexical filtra por projeto

### Qdrant

Cada point recebe project_namespace

A busca vetorial cria filtro obrigatório de namespace

### get_context

A consulta SQL exige simultaneamente

```text
chunk_id = ?
c.project_id = ?
d.project_id = ?
```

Logo saber o chunk_id de outro projeto não concede acesso

## Teste negativo

Criado

`tests/test_rag_015_scope_security.py`

Casos

1. project A não recebe project B via lexical
2. project A não recebe project B em nenhuma collection vetorial
3. project B não recebe project A
4. get_context bloqueia chunk_id cross-project
5. get_context permite chunk do próprio projeto

Execução observada

```text
Ran 5 tests in 1.221s
OK
```

## Alterações de produção

Nenhuma correção de produção foi necessária nesta fase

Os filtros de namespace implementados nos marcos anteriores já satisfaziam o requisito

RAG-015-B adiciona a prova negativa consolidada de segurança

## Arquivos

Criado

`tests/test_rag_015_scope_security.py`

Criado

`docs/RAG_015_B_SCOPE.md`

## Critério de aceitação

RAG-015-B está concluído quando

- dois projetos coexistem no mesmo SQLite/Qdrant
- conteúdo adversarial é igual entre projetos
- vetores adversariais são iguais
- FTS5 não vaza
- text vector não vaza
- code vector não vaza
- HYBRID não vaza
- get_context não aceita chunk cross-project
- busca no próprio projeto continua funcional
- testes passam
- suíte RAG passa
- git diff check passa

## Próximo passo

`RAG-015-C — Path traversal`

Bloquear caminhos fora das raízes autorizadas e provar bypasses negativos em formatos POSIX e Windows
