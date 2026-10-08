# RAG-016-A — Soak de indexação e consultas repetidas

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-016-production`

## Objetivo

Executar repetidamente indexação e consultas antes dos canários específicos de CPU GPU e restart

Requisito do handoff

`Rodar consultas/indexações repetidas`

## Escopo desta fase

RAG-016-A mede estabilidade de

- descoberta de fontes
- denylist
- secret scan
- chunking real
- IDs determinísticos
- SQLite
- FTS5
- Qdrant Local
- namespace
- upsert idempotente
- HYBRID candidate collection
- RRF
- dedup

Os modelos locais não são carregados neste soak

Isso é intencional

`RAG-016-C` é o canário CPU-only

`RAG-016-D` é o canário GPU

## Harness

Criado

`rag/benchmark/soak.py`

API

`run_storage_retrieval_soak()`

Resultado

`SoakResult`

O harness usa storage temporário e nunca substitui o índice persistente de produção

## Indexação repetida

A execução oficial usou

```text
index_cycles = 10
```

Em cada ciclo

1. executa o planejamento real de fontes
2. aplica políticas de segurança
3. executa chunking
4. grava SQLite
5. reconstrói/verifica FTS5
6. seleciona chunks text/code
7. faz upsert determinístico em Qdrant
8. confirma que a quantidade de points não cresce

Critério

a quantidade de documents e chunks deve permanecer exatamente igual entre ciclos

Se crescer ou diminuir sem mudança de fonte o soak falha

## Queries repetidas

Execução oficial

```text
query_cycles = 1000
```

Cada ciclo executa

```text
FTS5
+
text vector
+
code vector
↓
HYBRID candidates
↓
RRF
↓
dedup
↓
top-k
```

O ranking final de uma consulta idêntica deve permanecer determinístico

A primeira assinatura vira baseline

Qualquer alteração posterior faz o soak falhar

## Resultado observado

Arquivo

`benchmarks/rag016_soak_latest.json`

Runner

`benchmarks/run_rag016_soak.py`

Execução real

```text
index_cycles = 10
query_cycles = 1000

documents = 188
chunks = 7527

text_vector_points = 1
code_vector_points = 1
```

Os points são probes idempotentes

Mesmo após dez ciclos continuaram exatamente

```text
text = 1
code = 1
```

Não houve crescimento por duplicação

## Ranking

As 1000 consultas produziram a mesma assinatura final

A assinatura observada contém oito chunk IDs

Ela foi preservada byte a byte no resultado JSON

Nenhum ciclo apresentou mudança de ordem ou conjunto

## Tempo

Tempo total observado

```text
344.047469 s
```

aproximadamente

`5 min 44 s`

O processo terminou normalmente com exit code 0

## Memória do runner

```text
RSS start = 29163520 bytes
RSS end   = 97034240 bytes
delta     = 67870720 bytes
```

Aumento aproximado

`64.7 MiB`

Esse valor inclui runtime Python SQLite e Qdrant Local mantidos durante o soak

Não representa RAM de modelos porque nenhum modelo foi carregado nesta subfase

## Tamanho do índice temporário

```text
SQLite = 15839232 bytes
Qdrant = 46113 bytes
total  = 15885345 bytes
```

aproximadamente

`15.15 MiB`

O Qdrant contém somente os dois probe vectors necessários para testar idempotência e retrieval

## Teste automático reduzido

Criado

`tests/test_rag_016_soak.py`

O teste reduzido usa projeto temporário real com

- Markdown
- Python
- SQLite
- FTS5
- Qdrant Local

Executa

```text
3 index cycles
25 query cycles
```

Resultado observado

```text
Ran 2 tests in 0.778s
OK
```

Também valida parâmetros inválidos

## Invariantes provados

1 indexação repetida não multiplica documentos

2 indexação repetida não multiplica chunks

3 upsert vetorial determinístico não multiplica points

4 collections text e code permanecem estáveis

5 query HYBRID repetida é determinística

6 RRF e dedup não mudam ranking entre ciclos idênticos

7 fontes originais não são alteradas pelo harness

8 soak usa storage temporário e não promove automaticamente o índice para produção

## Relação com o gate RAG-014

O soak estável não muda o resultado de qualidade do benchmark

`PRODUCTION READINESS`

continua condicionado ao gate congelado no RAG-014

RAG-016-A prova estabilidade operacional do caminho medido

não prova que Recall/MRR já atingiram o threshold

## Arquivos

Criado

`rag/benchmark/soak.py`

Atualizado

`rag/benchmark/__init__.py`

Criado

`tests/test_rag_016_soak.py`

Criado

`benchmarks/run_rag016_soak.py`

Criado

`benchmarks/rag016_soak_latest.json`

Criado

`docs/RAG_016_A_SOAK.md`

## Critério de aceitação

RAG-016-A está concluído quando

- indexação é repetida múltiplas vezes
- counts permanecem estáveis
- vector upsert é idempotente
- consultas são repetidas múltiplas vezes
- ranking permanece determinístico
- execução longa termina sem erro
- teste reduzido passa
- suíte RAG passa
- git diff check passa

## Próximo passo

`RAG-016-B — Restart`

Provar recuperação após fechar e reabrir CodeBridge sem depender de estado volátil do processo anterior
