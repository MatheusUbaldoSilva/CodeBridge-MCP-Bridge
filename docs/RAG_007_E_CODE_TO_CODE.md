# RAG-007-E — Code → code

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-007-jina-code`

## Objetivo

Provar busca por trecho de código semanticamente semelhante usando a tarefa oficial `CODE2CODE` do Jina Code 1.5B.

## Fluxo

```text
query code
↓
CODE2CODE QUERY
↓
corpus SourceType.CODE
↓
CODE2CODE PASSAGE
↓
cosine similarity
↓
ranking determinístico
↓
SearchResult verificável
```

## Prefixes

Query:

`Find an equivalent code snippet given the following code snippet:\n`

Passage:

`Candidate code snippet:\n`

O 007-E não reutiliza o prefixo NL2CODE.

## Reuso arquitetural

O mesmo núcleo de ranking de cosseno do 007-D agora recebe a task explicitamente.

Wrappers públicos:

- `rank_nl_to_code`
- `rank_code_to_code`
- `retrieve_nl_to_code`
- `retrieve_code_to_code`

Isso evita duas implementações independentes de validação, score e tie-break.

## Ranking

Permanece:

1. cosine score desc;
2. path;
3. line_start;
4. chunk_id.

Retrieval modes do 007-E:

- `CODE_VECTOR_IN_MEMORY`
- `CODE2CODE`

## Persistência

Nenhum vetor é persistido nesta fase.

Qdrant, HNSW ou outro índice vetorial continuam fora de escopo até RAG-009.

## Implementação

Atualizado:

- `rag/ranking/code_similarity.py`
- `rag/ranking/__init__.py`
- `rag/retrieval/code_semantic.py`
- `rag/retrieval/__init__.py`

Criado:

- `tests/test_rag_code_to_code_retrieval.py`

## Critério de aceitação

- QUERY usa CODE2CODE;
- PASSAGE usa CODE2CODE;
- ranking por cosseno permanece determinístico;
- provenance é preservada;
- NL2CODE continua funcionando;
- smoke real encontra código equivalente em top-1;
- nenhum vector store é antecipado;
- suíte RAG passa;
- diff check passa.


## Compatibilidade retroativa do RAG-007-D

Durante a primeira validação do refactor, os 10 testes novos do CODE2CODE passaram, mas o teste legado do RAG-007-D falhou no import porque o nome público:

`CODE_NL_RETRIEVAL_MODE`

havia sido substituído internamente por:

`CODE_VECTOR_RETRIEVAL_MODE`

O valor semântico era o mesmo, mas o contrato público já estava congelado no 007-D.

A correção foi manter:

```text
CODE_NL_RETRIEVAL_MODE = CODE_VECTOR_RETRIEVAL_MODE
```

como alias retrocompatível.

Depois da correção:

```text
Ran 20 tests
OK
```

incluindo simultaneamente:

- `test_rag_code_to_code_retrieval`
- `test_rag_code_nl_retrieval`

Portanto o 007-E não quebra o fluxo NL2CODE anterior.

## Smoke real CODE → code

O smoke foi executado contra o Q8_0 real em `CUDA0`.

Corpus:

1. `wait`
   - path `author_mcp/mcp_server.py`
   - symbol `codebridge_wait`
   - trecho contendo `EXECUTION_V2_WAIT`

2. `cancel`
   - path `app_rewrite/windows_terminal_session.py`
   - symbol `cancel_current`
   - trecho com `_cancel_requested = True` e `send_ctrl_c()`

3. `config`
   - path `author_mcp/mcp_server.py`
   - symbol `_normalize_output_mode`
   - distrator

### Consulta de código 1

Trecho equivalente:

```python
exchange = _safe_exchange(
    "EXECUTION_V2_WAIT",
    {
        "execution_id": eid,
        "timeout_ms": ms,
    },
)
```

Resultado:

```text
EXPECTED=wait
TOP=wait
RANK=wait:0.810508,cancel:0.297400,config:0.091463
```

Target esperado em rank 1.

### Consulta de código 2

Trecho equivalente:

```python
if not self._cancel_requested:
    self._cancel_requested = True
    self.send_ctrl_c()
```

Resultado:

```text
EXPECTED=cancel
TOP=cancel
RANK=cancel:0.988357,wait:0.271516,config:0.066393
```

Target esperado em rank 1.

Resumo:

```text
DEVICE=CUDA0
PID=11652
UNLOAD=UNLOADED
```

O PID é somente o valor desta execução de teste.

## Leitura dos resultados

As duas consultas por trecho de código encontraram o candidato semanticamente equivalente em top-1.

Margens:

- wait: 0.810508 contra 0.297400;
- cancel: 0.988357 contra 0.271516.

O CODE2CODE apresentou separação forte neste corpus controlado.

RAG-007-E não congela threshold global.

A fase prova ranking relativo e task semantics corretas.

## Validação final

Testes específicos do RAG-007-E + regressão do 007-D:

```text
Ran 20 tests
OK
```

Suíte RAG completa:

```text
Ran 380 tests
OK
```

Git whitespace audit:

```text
git diff --check e370bf80153cd4b75ad78b7aef2f303a17f3e36d..HEAD
exit_code = 0
```

Worktree:

```text
## HEAD (no branch)
```

sem alterações locais.

## Estado final do RAG-007-E

- task CODE2CODE explícita;
- query prefix CODE2CODE usado;
- passage prefix CODE2CODE usado;
- ranking compartilhado sem duplicação;
- NL2CODE permaneceu retrocompatível;
- wait equivalente ficou top-1;
- cancel equivalente ficou top-1;
- provenance preservada;
- top_k e tie-break continuam determinísticos;
- modelo retornou UNLOADED;
- nenhum vector store persistente foi antecipado;
- 380 testes RAG passaram;
- diff check passou.

RAG-007-E está pronto para fechamento.
