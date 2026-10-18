# RAG-LAB.04 — Situação e pendências após os testes de concorrência

Data: 2026-10-18
Escopo: fixture sintética exclusivamente

## Evidências acrescentadas

- 5b6f724: WAL interno Qdrant criado na gravação de report.json era aceito no snapshot. Agora guarda final anterior à publicação bloqueia sidecars SQLite principal e Qdrant.
- 00b5088: catalog_synthetic_stores e inspect_fixture_handles bloqueiam sidecars internos Qdrant.
- 3517d86: contrato e limites documentados.
- 37c71ad: três sufixos SQLite principal criados na gravação de report.json são rejeitados.
- 7414f24: WAL Qdrant introduzido durante hashing é rejeitado pelos dois probes.
- Regressão final de backend: 385 PASS, sendo 257 offline, 83 generation, 7 preflight e 38 incremental.

## O que não está comprovado

Checagens pontuais antes de publicação não são lock global do Windows.
A cobertura dos formatos de dados é restrita à versão atual e às fixtures descartáveis.
Ainda não existe observação independente completa de todos os processos, writers, handles e mappings em produção.
Não há autorização de janela de manutenção, nem aprovação de parada e backup reais.

## Decisão

Fechamento normativo RAG-LAB.04: PARCIAL, pendências explícitas acima.
RAG-LAB.05 real: NÃO INICIADA, depende de gates prévios e decisão humana.

copy_authorized=false
all_handles_closed=false
production_quiescence_proven=false
production_backup=BLOCKED
