RAG-LAB.04 — Matriz de evidencias e pendencias normativas

Escopo 100% sintético 2026-10-17
04-A ID independente e no-overwrite tests/test_offline_lab04_independent_capture.py commit 301d959
04-B validacao cruzada dos tres stores tests/test_offline_lab04_cross_store_capture.py commit 993668d
04-C restauracao isolada em destinos distintos tests/test_offline_lab04_independent_restore.py commit ddb0717
04-C validacao da copia em novo processo Python tests/test_offline_lab04_external_restore_validation.py commit 7dd1609
04-D copia interrompida staging removido e restore anterior preservado tests/test_offline_lab04_rollback_fault.py commit c544207
04-D hash omitido e arquivo extra tests/test_offline_lab04_adversarial_completeness.py commit 5c8a63e
04-E bloqueio de metadados falsos e destinos invalidos tests/test_offline_lab04_restore_boundaries.py commit e4f4b64

Cobertura preexistente nao equivalente a fechamento normativo completo
Writer aberto tests/test_offline_fixture_snapshot.py
Symlink hardlink e mutacao durante catalogo tests/test_offline_store_tree_catalog.py
Sidecars e relatorio adulterado tests/test_offline_fixture_restore.py

Lacunas restantes a comprovar
Matriz integrada de todos tipos reais Qdrant checkpoint e sidecars
Cenarios concorrentes entre snapshot e restore em um mesmo caso end-to-end
Auditoria de handles/mmap globais e parada real externa dependem de gate futuro e autorizacao humana

Ultima bateria integrada 370 backend PASS 242 offline 83 generation 7 preflight 38 incremental
Situacao normativa PARCIAL ate encerramento das lacunas
copy_authorized=false
all_handles_closed=false
production_quiescence_proven=false
production_backup=BLOCKED
