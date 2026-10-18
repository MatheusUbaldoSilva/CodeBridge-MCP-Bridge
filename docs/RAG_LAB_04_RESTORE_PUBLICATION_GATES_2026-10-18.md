# RAG-LAB.04 — Restauração sintética e sidecars tardios

Data: 2026-10-18
Escopo: somente fixtures sintéticas, sem operações de produção

## Lacuna reproduzida

Um Qdrant storage.sqlite-wal podia surgir no payload depois de validate_incremental_bundle(copy) e antes do rename final da restauração, permitindo publicar diretório apesar de mudança tardia. O primeiro ensaio falhou conforme esperado, indicando ausência de guarda final.

## Correção e testes

- d18a7d0: guarda no offline_fixture_restore.py valida, antes da publicação, ausência de sidecars SQLite principais e internos Qdrant tanto no payload de origem quanto na cópia temporária. Teste tests/test_offline_lab04_restore_publish_sidecar.py.
- f72cecc: matriz de -wal/-shm/-journal SQLite principal aparecendo no payload após validação.
- 6f53226: matriz de -wal/-shm/-journal Qdrant aparecendo no staging após validação.
- fb0f552: matriz de -wal/-shm/-journal SQLite principal aparecendo no staging após validação.

Última regressão integrada backend: 389 PASS = 261 offline + 83 generation + 7 preflight + 38 incremental.

## Limites

O teste inicialmente injetado dentro da própria chamada os.rename ilustrou uma janela impossível de eliminar somente com preflight pontual. Os testes corrigidos injetam entre a última validação e o rename; demonstram o bloqueio naquele ponto, não atomicidade universal contra writers externos.

Não há observador externo com prova integral de todos os writers, readers, handles ou mappings Windows. O teste de fixture não equivale à conformidade com todas as versões e checkpoints reais do Qdrant. Nenhum backup real foi executado e nenhum processo de produção foi encerrado.

Fechamento normativo RAG-LAB.04: PARCIAL.
RAG-LAB.05 manutenção real: BLOQUEADA, depende de autorização humana e provas externas.

copy_authorized=false
all_handles_closed=false
production_quiescence_proven=false
production_backup=BLOCKED
