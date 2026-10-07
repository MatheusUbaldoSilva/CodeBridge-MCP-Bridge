# RAG-007-D — Consultas NL → code

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-007-jina-code`

## Objetivo

Provar consultas em linguagem natural contra um corpus de código usando o Jina Code 1.5B.

Exemplos obrigatórios do handoff:

- onde valida ownership do item?
- onde controla cancelamento?
- onde o runtime acorda o wait?

## Limite desta fase

RAG-007-D NÃO cria índice vetorial persistente.

O fluxo de prova é deliberadamente in-memory:

```text
query NL
↓
embedding NL2CODE QUERY
↓
chunks CODE fornecidos pelo chamador
↓
embedding NL2CODE PASSAGE
↓
cosine similarity
↓
ordenação determinística
↓
SearchResult com provenance
```

O vector store de produção continua reservado ao RAG-009.

## Separação retrieval / ranking

`rag/retrieval/code_semantic.py`

- valida consulta e corpus;
- gera query embedding;
- gera passage embeddings;
- delega ordenação.

`rag/ranking/code_similarity.py`

- calcula cosine similarity;
- valida identidade/provenance;
- ordena;
- aplica top_k;
- devolve `SearchResult`.

Essa divisão segue o layout de módulos congelado no RAG-001-B.

## Ranking determinístico

Ordenação primária:

`score desc`

Empates:

1. path
2. line_start
3. chunk_id

O tie-break não cria verdade oficial; apenas garante resultado reprodutível.

## Resultado

Cada hit preserva:

- chunk_id
- document_id
- conteúdo original
- SourceMetadata original
- cosine score
- rank
- stale=false

Retrieval modes:

- CODE_VECTOR_IN_MEMORY
- NL2CODE

## Relação com a fonte real

O resultado semântico é candidato.

O princípio continua:

```text
RAG encontra
→ CodeBridge verifica fonte real
→ Git/arquivo prova estado atual
→ IA decide/executa
```

## Corpus do smoke real

A auditoria do repositório encontrou casos reais para:

- `codebridge_wait` em `author_mcp/mcp_server.py`;
- cancelamento em `author_mcp/mcp_server.py` e `app_rewrite/windows_terminal_session.py`.

O repositório CodeBridge não contém a regra de ownership de item do projeto Metin2.

Portanto o smoke final usa:

- wait real do CodeBridge;
- cancelamento real do CodeBridge;
- fixture C++ controlada para ownership de item;
- distratores adicionais.

Isso será registrado explicitamente no resultado do smoke.

## Implementação

Criado:

- `rag/retrieval/__init__.py`
- `rag/retrieval/code_semantic.py`
- `rag/ranking/__init__.py`
- `rag/ranking/code_similarity.py`
- `tests/test_rag_code_nl_retrieval.py`

## Critério de aceitação

- fluxo NL2CODE explícito;
- corpus somente CODE;
- cosine score preservado;
- top_k testado;
- tie-break determinístico;
- SearchResult preserva fonte/provenance;
- três consultas do handoff testadas no modelo real;
- target esperado em top-1 para os três casos;
- nenhum vector store persistente antecipado;
- suíte RAG passa;
- diff check passa.


## Smoke real NL → code

O smoke foi executado contra o Q8_0 real em `CUDA0`.

Corpus com cinco candidatos:

1. `ownership`
   - fixture controlada C++ do projeto Metin2
   - símbolo `CHARACTER::CanMoveItem`
   - valida `item->GetOwner() != this`

2. `cancel`
   - código real do CodeBridge
   - `app_rewrite/windows_terminal_session.py`
   - símbolo `cancel_current`
   - linhas 3432-3472

3. `wait`
   - código real do CodeBridge
   - `author_mcp/mcp_server.py`
   - símbolo `codebridge_wait`
   - linhas 967-1035

4. `logging`
   - distrator do terminal Windows

5. `config`
   - distrator do MCP server

### Consulta 1

`onde valida ownership do item?`

Resultado

```text
TOP=ownership|EXPECTED=ownership
RANK=ownership:0.539577,cancel:0.062257,logging:0.051984,wait:0.013939,config:-0.057214
```

Target esperado em rank 1.

### Consulta 2

`onde controla cancelamento?`

Resultado

```text
TOP=cancel|EXPECTED=cancel
RANK=cancel:0.544087,logging:0.314541,wait:0.215576,ownership:0.168250,config:0.036934
```

Target esperado em rank 1.

### Consulta 3

`onde o runtime acorda o wait?`

Resultado

```text
TOP=wait|EXPECTED=wait
RANK=wait:0.444449,logging:0.342597,cancel:0.335562,config:0.074582,ownership:0.065294
```

Target esperado em rank 1.

Resumo do smoke

```text
DEVICE=CUDA0
PID=1200
ALL_TOP1=True
UNLOAD=UNLOADED
```

O PID é somente o valor da execução de teste.

## Leitura dos resultados

Os três exemplos do handoff acertaram o candidato esperado em top-1.

As margens observadas foram:

- ownership: 0.539577 contra 0.062257 no segundo colocado;
- cancelamento: 0.544087 contra 0.314541;
- wait: 0.444449 contra 0.342597.

O caso wait teve a menor margem e continuará sendo um bom caso de regressão para fases posteriores.

RAG-007-D não define threshold mínimo de aceitação.

A fase prova ranking relativo sobre corpus conhecido.

Threshold e fusão com outras modalidades não são congelados aqui.

## Observação sobre o script de smoke

O script temporário foi gravado em `%TEMP%` para contornar limite de tamanho do comando do CodeBridge.

A primeira chamada direta do arquivo falhou antes de qualquer inferência porque o Python usou `%TEMP%` como raiz de import e não encontrou o pacote `rag`.

A mesma prova foi então executada via `python -c` a partir do worktree, mantendo o checkout no `sys.path`.

Esse erro de montagem não alterou código nem resultado do modelo.

## Validação final

Testes específicos do RAG-007-D

```text
Ran 10 tests
OK
```

Suíte RAG completa

```text
Ran 370 tests
OK
```

Git whitespace audit

```text
git diff --check 15af7a6c3e6d5480e0d96843508af96fa1037d00..HEAD
exit_code = 0
```

Worktree

```text
## HEAD (no branch)
```

sem alterações locais.

## Estado final do RAG-007-D

- NL2CODE QUERY implementado;
- NL2CODE PASSAGE implementado;
- cosine ranking determinístico implementado;
- top_k implementado;
- SearchResult preserva fonte e provenance;
- retrieval e ranking mantidos em módulos separados;
- ownership ficou top-1;
- cancelamento ficou top-1;
- wait ficou top-1;
- 3 de 3 consultas obrigatórias passaram;
- modelo retornou a UNLOADED;
- nenhum vector store persistente foi antecipado;
- 370 testes RAG passaram;
- diff check passou.

RAG-007-D está pronto para fechamento.
