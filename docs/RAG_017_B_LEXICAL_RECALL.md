# RAG-017-B — Normalização de consultas e recall lexical

## Resultado
Subfase de melhoria geral da busca lexical, sem regras especiais para IDs de queries e sem alteração de thresholds.

- Problema: a busca FTS5 aplicava somente correspondência literal da frase completa, frequentemente retornando zero candidatos quando o usuário formulava perguntas naturais.
- Mudança em `rag/index/lexical_ranking.py`: mantém correspondência literal em primeiro lugar; quando sobram vagas, amplia a consulta para termos lexicais normalizados (casefold, deduplicação, remoção de stopwords e tokens menores que três caracteres, com limite geral de 16 termos).
- Todos os termos são encapsulados como literais FTS5; o fallback usa a mesma consulta SQL e preserva filtros de projeto, fonte, caminho e branch; mantém resultados exatos à frente, sem duplicar chunks.
- Não houve alteração da busca semântica, classificador, vetores, chunking ou pesos do ranking BM25.

## Medição e limites
- Referência lexical antiga RAG-014: 0% Recall@5, 0% Recall@10, MRR 0.0.
- RAG-017-B lexical isolado em 100 queries: Recall@5 **0.59**, Recall@10 **0.70**, MRR **0.492591**.
- O corpus atual inclui 201 documentos / 8693 chunks (o corpus lexical da referência tinha 177 documentos / 6901 chunks). Por isso, a diferença observada não constitui experimento A/B sobre corpus idêntico.
- Script de reprodução: `benchmarks/run_rag017b_lexical.py`; dados `benchmarks/rag017b_lexical_latest.json`.
- Não foi repetido o benchmark híbrido integral após a mudança; portanto **não afirmar aprovação do gate de produção**. A validação do benchmark híbrido fica para RAG-017-F, com metas originais preservadas.
- O índice persistente de produção permanece não READY.

## Segurança e validação
- `tests/test_rag_017_b_lexical.py`: fallback em pergunta natural; isolamento entre projetos; FTS literal mesmo com operador injetado; caminho restritivo; consulta somente com stopwords.
- Rodar suíte completa `python -m unittest discover -s tests -p test_rag_*.py -q`.
- Revisar diff, git diff --check, commit, push e pós-commit.

## Próxima etapa
RAG-017-C auditar rotas TEXT/CODE/HYBRID e avaliar os erros gerais do classificador, usando failure matrix RAG-017-A.
