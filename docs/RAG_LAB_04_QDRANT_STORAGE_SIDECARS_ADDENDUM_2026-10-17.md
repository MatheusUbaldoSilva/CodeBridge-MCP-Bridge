# RAG-LAB.04 — Adendo dos arquivos Qdrant locais

Data 2026-10-17

Inventário criado em fixture descartável pela implementação Qdrant local instalada:
- qdrant/.lock
- qdrant/meta.json
- qdrant/collection/code/storage.sqlite
- qdrant/collection/text/storage.sqlite

Este inventário comprova apenas a estrutura criada por essa versão e essa fixture. Não representa todos os formatos e checkpoints Qdrant.

Lacuna reproduzida: a captura sintética aceitava storage.sqlite-wal, storage.sqlite-shm e storage.sqlite-journal na árvore Qdrant.

Correção d048854: captura e restauração conservadoras rejeitam os três tipos de sidecar SQLite internos; teste tests/test_offline_lab04_qdrant_sqlite_sidecars.py.

Validação adicional aaf3eb6: sidecar WAL surgindo entre o catálogo e a cópia faz a captura abortar sem publicar snapshot e limpa o staging; teste tests/test_offline_lab04_qdrant_late_wal.py.

Regressão integrada final 380 PASS = 252 offline + 83 generation + 7 preflight + 38 incremental.

Ainda não estão comprovados todos os tipos de checkpoint por versão, a observação global de handles Windows e mmap, ou a quiescência de produção.

copy_authorized=false
all_handles_closed=false
production_quiescence_proven=false
production_backup=BLOCKED
