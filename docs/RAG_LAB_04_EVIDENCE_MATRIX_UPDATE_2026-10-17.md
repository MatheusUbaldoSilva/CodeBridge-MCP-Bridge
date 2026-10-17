# RAG-LAB.04 — Atualização da matriz de evidências

Data: 2026-10-17
Escopo: apenas fixtures sintéticas, sem autorização de backup de produção

## Novas evidências desta sessão

- 2b66339 — testes/test_offline_lab04_concurrent_capture_restore.py: um processo externo detém generation_lock; captura e restauração recusadas até liberar bloqueio; recuperação posterior autorizada somente na fixture
- bc61df9 — tests/test_offline_lab04_sidecar_matrix.py: cada -wal, -shm e -journal recusa captura e restauração
- 9632362 — tests/test_offline_lab04_nested_qdrant_artifact.py: arquivo aninhado sintético preservado e adulteração detectada após snapshot
- c874047 — tests/test_offline_lab04_qdrant_link_boundaries.py: hardlink antes de captura e symlink adicionado ao backup bloqueados; exceção interna normalizada para OfflineFixtureRestoreError em rag/runtime/offline_fixture_restore.py

## Auditoria regressiva

Última regressão de backend: 249 offline + 83 generation + 7 preflight + 38 incremental = 377 PASS
Quatro incrementos versionados separadamente, revisão diff --cached --check e confirmação HEAD igual ao upstream

## Limites não encerrados

O arquivo de teste chamado checkpoint-lab é dado sintético e não representa um checkpoint real Qdrant
A matriz de formatos reais de checkpoint e sidecars internos Qdrant não foi exaustivamente comprovada
Não há comprovação de quiescência global dos processos Windows, handles, mappings ou leitores não cadastrados
O encerramento normativo de RAG-LAB.04 continua PARCIAL até validação dessas evidências

copy_authorized=false
all_handles_closed=false
production_quiescence_proven=false
production_backup=BLOCKED
