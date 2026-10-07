# RAG-010-D — Fusão determinística com Reciprocal Rank Fusion

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-010-hybrid-search`

## Objetivo

Fundir rankings heterogêneos sem comparar diretamente os scores crus de BM25 e Cosine

Requisito do handoff

`Começar com método determinístico preferencialmente Reciprocal Rank Fusion`

## Método escolhido

`Reciprocal Rank Fusion`

Implementação

`reciprocal_rank_fusion()`

Constante congelada

`DEFAULT_RRF_K = 60`

Fórmula

```text
RRF(chunk) = soma 1 / (k + posição_do_chunk_no_ranking)
```

A posição começa em 1

## Por que RRF

Os rankings atuais possuem escalas diferentes

- FTS5 BM25
- vetor textual Cosine
- vetor de código Cosine

RRF usa somente posição

Assim nenhum score bruto precisa ser normalizado ou calibrado nesta fase

## Identidade de fusão

A identidade exata é

`chunk_id`

Se o mesmo chunk aparece em mais de um ranking ele acumula contribuição de todos

Isso é necessário para a própria fusão

Não é a deduplicação semântica do RAG-010-E

Chunks diferentes com conteúdo parecido continuam separados nesta fase

## Retrieval modes

Quando o mesmo chunk aparece em múltiplas fontes os retrieval modes são unidos em ordem estável

Exemplo

```text
LEXICAL_FTS5_BM25
VECTOR_TEXT_COSINE
VECTOR_CODE_COSINE
```

## Consistência

Se o mesmo chunk_id aparecer com

- document_id diferente
- content diferente
- metadata diferente

a fusão rejeita o conflito

Isso evita esconder inconsistência de índice atrás do ranking final

## Duplicata dentro do mesmo ranking

Se o mesmo chunk_id aparecer duas vezes na mesma lista somente a primeira posição contribui

Um mecanismo de retrieval não pode aumentar artificialmente o score repetindo a mesma identidade

## Tie break

Ordenação final

1 maior score RRF
2 melhor posição individual
3 chunk_id em ordem lexical

Isso torna o resultado determinístico mesmo em empate total

## top_k

O corte é aplicado somente depois da fusão

Assim um chunk presente em múltiplas listas pode subir antes do truncamento

## Provas

Os testes validam

- chunk presente em múltiplos rankings sobe
- scores crus não alteram RRF
- empate é determinístico
- repetição na mesma lista conta uma vez
- near duplicate não é removido
- conflito do mesmo chunk é rejeitado
- top_k acontece depois da fusão
- entradas vazias são válidas

## Arquivos

Criado

`rag/ranking/rrf.py`

Atualizado

`rag/ranking/__init__.py`

Criado

`tests/test_rag_rrf.py`

Criado

`docs/RAG_010_D_RRF.md`

## Fronteiras

RAG-010-D não remove chunks quase iguais

Não usa similaridade de conteúdo para deduplicar

Não define threshold semântico

Esses pontos pertencem ao RAG-010-E

## Critério de aceitação

RAG-010-D está concluído quando

- RRF é determinístico
- k está congelado
- scores heterogêneos não são comparados diretamente
- chunk recorrente acumula evidência
- retrieval modes são preservados
- conflitos de identidade são rejeitados
- tie break é estável
- top_k é pós fusão
- testes específicos passam
- suíte RAG passa
- git diff check passa
