# P3 ? Colisao de artefato de recuperacao

Data 2026-10-21. Teste temporario test_preserved_pointer_collision_blocks_rollback_without_mutation verifica que rollback_pending_to_legacy nao sobrescreve arquivo recovered-pointer-<candidate>.json existente. Journal e ponteiro pendentes ficam identicos byte a byte; o arquivo anterior mantem o conteudo original. Resultado PASS, nenhuma alteracao de indice publico. O bloqueio permanece proposital ate operador resolver ambiguidade de estado.
