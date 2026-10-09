# RAG-017-I — Gate de produção: BLOCKED

## Critérios oficiais
Critérios do handoff: Recall@5, Recall@10, MRR, latência cold e warm, RAM, VRAM, tamanho do índice e thresholds **inalterados**. Limites congelados importados de `benchmarks/rag014_readiness_report.json`.

## Resultado auditado
O script `benchmarks/evaluate_rag017i_gate.py` confronta as métricas do benchmark completo RAG-017-F com os limites congelados e consulta o snapshot persistente atual. Evidência legível por máquina em `benchmarks/rag017i_production_gate.json`.

| Indicador | Medição | Limite | Resultado |
|---|---:|---:|---|
| Recall@5 | 0,77 | >= 0,80 | FAIL |
| Recall@10 | 0,83 | >= 0,90 | FAIL |
| MRR | 0,531817 | >= 0,60 | FAIL |
| Cold (estimado) | 3723,69 ms | <= 20000 ms | PASS |
| Warm p95 | 173,33 ms | <= 1000 ms | PASS |
| RAM (soma aproximada RSS) | 4.432.125.952 bytes | <= 6.442.450.944 | PASS |
| VRAM delta | 4214 MiB | <= 5120 MiB | PASS |
| Índice benchmark | 111.625.249 bytes | <= 2.147.483.648 | PASS |
| Índice persistente (SQLite+Qdrant+manifest) | 113.201.554 bytes | <= 2.147.483.648 | PASS |

Índice persistente: `READY`, SQLite `PRAGMA integrity_check = ok`, 210 documentos, 8761 chunks e 210 manifest entries.

**Decisão: gate de produção BLOCKED.** READY indica integridade técnica do índice, não liberação da qualidade semântica.

## Qualificações e limitações
- A evidência de qualidade é o benchmark semântico completo de RAG-017-F (100 queries), não uma segunda avaliação sobre o índice persistente. O corpus mudou; não reivindicar equivalência.
- Cold é uma estimativa do benchmark; RAM combina RSS registrados e é aproximação, não medição simultânea garantida.
- O aplicativo instalado não teve os executores registrados automaticamente e a atualização incremental automática ainda não está ativa.
- Nunca ajustar limiares, reduzir dataset ou selecionar apenas queries favoráveis para obter aprovação.

## Fechamento da subfase
A subfase I termina como **auditoria completa com parecer de reprovação de produção**. O RAG-017-J deve registrar formalmente o gate bloqueado e preservar o roadmap de melhoria da qualidade antes da ativação geral. O fechamento técnico exige testes, diff, commit, push e auditoria pós-commit.
