# RAG-010-E — Deduplicação de resultados quase iguais

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-010-hybrid-search`

## Objetivo

Evitar que chunks praticamente iguais dominem o top-k depois da fusão

Requisito do handoff

`Evitar que chunks praticamente iguais dominem o top-k`

## Estratégia

A deduplicação é determinística e ocorre depois do ranking

Função

`deduplicate_ranked_results()`

A primeira ocorrência no ranking final é preservada

Resultados posteriores considerados equivalentes são suprimidos

## Nível 1 — igualdade normalizada

O conteúdo é normalizado com

- Unicode NFKC
- casefold
- tokenização por palavras
- remoção de diferenças puramente de pontuação e espaço

Exemplos equivalentes

```text
Cancel Current Request
cancel-current   request
```

Esse caso gera

`NORMALIZED_EXACT`

com similaridade 1.0

## Nível 2 — quase duplicata longa

Para chunks com tamanho suficiente é usado Jaccard determinístico de shingles de tokens

Contrato congelado inicial

```text
threshold = 0.90
min_tokens = 12
shingle_size = 5
```

Motivo do mínimo de tokens

Trechos muito curtos semelhantes não devem ser colapsados agressivamente

Exemplo

`cancel request now`

e

`cancel request later`

continuam separados

## Resultado estruturado

`DeduplicationOutcome`

contém

```text
results
suppressed
```

Cada item suprimido registra

- suppressed_chunk_id
- kept_chunk_id
- similarity
- reason

Isso preserva auditabilidade da remoção

## Ordem

A deduplicação respeita a ordem já estabelecida pelo ranking

O primeiro resultado vence

Scores não são recalculados

Depois da supressão os ranks são compactados para

```text
1 2 3 ...
```

## top_k

O corte acontece depois da deduplicação

Isso é importante para não perder diversidade

Exemplo

```text
1 A
2 A duplicado
3 C
4 D
```

com top_k 2

resultado

```text
1 A
2 C
```

e não apenas A

## Relação com RRF

RAG-010-D já agrega ocorrência do mesmo `chunk_id` em vários rankings

RAG-010-E trata outro problema

chunks com IDs diferentes mas conteúdo igual ou quase igual

Portanto

```text
RRF
↓
ranking fundido
↓
deduplicação near duplicate
↓
top-k final
```

## Fronteira conservadora

Não existe embedding extra para decidir duplicidade

Não existe LLM

Não existe paraphrase detection

A política é textual e determinística

Isso evita apagar resultados semanticamente diferentes por uma heurística agressiva

## Provas

Os testes validam

- igualdade normalizada
- near duplicate longo
- trecho curto semelhante preservado
- conteúdo distinto preservado
- primeiro resultado vence
- score original é preservado
- ranks são compactados
- top_k ocorre depois da deduplicação
- opções inválidas são rejeitadas

## Arquivos

Criado

`rag/ranking/dedup.py`

Atualizado

`rag/ranking/__init__.py`

Criado

`tests/test_rag_dedup.py`

Criado

`docs/RAG_010_E_DEDUP.md`

## Critério de aceitação

RAG-010-E está concluído quando

- duplicata normalizada é removida
- near duplicate longo pode ser removido
- chunks curtos não são colapsados agressivamente
- resultado preservado é sempre o melhor ranqueado
- supressão fica auditável
- top_k ocorre após dedup
- testes específicos passam
- suíte RAG passa
- git diff check passa

Depois desta fase falta somente o benchmark exigido para o fechamento formal do RAG-010
