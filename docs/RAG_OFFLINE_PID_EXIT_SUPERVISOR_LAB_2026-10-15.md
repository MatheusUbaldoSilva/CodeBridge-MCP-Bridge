# Central RAG   Supervisor externo de saída de PIDs (laboratório)

Estado: IMPLEMENTAÇÃO EXPERIMENTAL, SOMENTE LEITURA.

O módulo `rag.runtime.offline_pid_exit_supervisor` recebe identidades
capturadas por `offline_pid_identity_audit` e exige confirmação de ausência
em pelo menos duas amostras consecutivas. Compara PID, horário de criação e
fingerprint SHA-256 do caminho do executável. PID reutilizado com identidade
diferente bloqueia. Inventário indisponível, identidades sem campos mínimos
ou processo persistente bloqueiam por segurança.

`EXPECTED_PIDS_ABSENT_UNPROVEN` significa SOMENTE que aqueles PIDs
esperados não apareceram nas amostras. Não demonstra que todos os
consumidores do índice foram encontrados, que mmap/handles foram liberados
ou que SQLite/Qdrant/manifesto formam um snapshot consistente.

Todas as saídas mantêm `copy_authorized=false`,
`production_quiescence_proven=false` e
`all_handles_closed=false`. O módulo não mata nem encerra processos.

Próximo marco: supervisor externo com acompanhamento de processos
filhos/herdados e verificação do catálogo completo de handles em laboratório;
depois auditoria separada da consistência dos três armazenamentos. Jamais
autorizar backup real pelo resultado deste módulo.
