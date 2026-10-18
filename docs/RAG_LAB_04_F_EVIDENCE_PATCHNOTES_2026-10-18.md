# RAG-LAB.04 — Evidencias e patch notes (2026-10-18)

Escopo EXCLUSIVO: fixture descartavel codebridge-rag-generation-test.

04-A: captura independente, sem overwrite e com origem preservada — tests/test_offline_lab04_independent_capture.py.
04-B: tres stores, manifest, sidecars e hashes cobertos em fixtures; formatos de checkpoints Qdrant por versao NAO exauridos.
04-C: restore clean-room, outro processo valida, sem ativar — tests/test_offline_lab04_external_restore_validation.py.
04-D: negativos de corrupcao, arquivos extras, writers e races — test_offline_lab04_adversarial_completeness.py e suites associadas.
04-E: rollback, limpeza de staging, ponteiro inalterado — test_offline_lab04_rollback_fault.py.
04-F: diff, regressao, commits, push, checkpoint e este patch note. Fechamento NORMATIVO PARCIAL.

## Patch notes recentes

51b71e7 — rag/runtime/offline_fixture_restore.py: rehash de copy imediatamente antes de publicar; teste test_offline_lab04_restore_staging_content_race.py reproduziu falha RED e validou GREEN.
2521750 — mesmo modulo: report.json lido como bytes e rechecado antes de publicar; test_offline_lab04_restore_report_mutation.py confirmou rejeicao de metadados adulterados.
56158d3 — rag/runtime/offline_restore_equivalence.py: bloqueia sidecars internos Qdrant -wal, -shm, -journal mesmo com hashes iguais; test_offline_lab04_equivalence_qdrant_sidecars.py RED/GREEN.

Regressao backend: 393 PASS (265 offline, 83 generation, 7 preflight, 38 incremental); zero falhas.
Qt test_rag_panel_qt_preview.py NAO EXECUTADO: PySide6 ausente do Python 3.13. Nenhuma dependencia instalada.

## Limitacoes

Qdrant local observado na fixture: .lock, meta.json, collection/code/storage.sqlite e collection/text/storage.sqlite. Nao representa todos os checkpoints reais ou versoes.
Os testes de race sao pontuais, nao provam quiescencia global ou ausencia de handles, mmap e writers externos. UI e MCP reais nao foram parados. Nenhuma copia de producao foi autorizada.
RAG-LAB.04 permanece PARCIAL. RAG-LAB.05 real BLOQUEADA ate evidencia externa e aprovacao humana especifica.

copy_authorized=false
all_handles_closed=false
production_quiescence_proven=false
production_backup=BLOCKED
