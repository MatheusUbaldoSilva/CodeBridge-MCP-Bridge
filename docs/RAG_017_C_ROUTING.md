# RAG-017-C — Auditoria das rotas TEXT/CODE/HYBRID

## Implementação
Revisão geral das regras de classificação em `rag/runtime/query_classifier.py`. O algoritmo continuou determinístico, sem modelos, I/O, Git ou leitura de índice.

- Padrões passam a corresponder a palavras/frases completas (com bordas Unicode), evitando falsos positivos como `code` dentro de `CodeBridge`.
- Perguntas naturais sobre comportamento de implementação, funções, retrievers e verificadores passam a receber sinal explícito de CODE quando não houver indicação concorrente de documentação.
- Prioridade mantida: formatos exatos -> escopo explícito -> indícios -> TEXT padrão. Não foram introduzidos tratamentos por identificador de query.

## Medição no dataset congelado
`benchmarks/audit_rag017c_routes.py` compara os 100 enunciados com as rotas do replay RAG-017-A e grava `benchmarks/rag017c_route_audit.json`.

| Rota | Antes | Depois |
| --- | ---: | ---: |
| CODE | 30 | 38 |
| TEXT | 65 | 58 |
| HYBRID | 5 | 4 |

19/100 rotas mudaram. Na categoria de código, CODE passou de 14 para 20 entre 25 queries; em código PT-BR, de 5 para 9 entre 10. Categorias servem somente como indicadores heurísticos e não são gabarito de rota. Alguns indícios podem exigir novo ajuste após auditoria vetorial.

## Qualidade e limites
Mudanças de rota **não equivalem** a ganho comprovado de Recall/MRR. O benchmark híbrido com modelos reais deve ser repetido na regressão integrada RAG-017-F. Índice persistente ainda não READY; gate de produção permanece BLOCKED e limiares não foram alterados.

## Verificações
- `tests/test_rag_017_c_classifier.py`: fronteiras de palavras, perguntas CODE em inglês/PT-BR, precedência de docs/escopo/lexical e integridade do relatório.
- Suite completa RAG; sintaxe Python; Git diff --check; commit/push; revisão pós-commit.

Próxima etapa: RAG-017-D, diagnóstico da busca vetorial e do chunking.
