# RAG V1.03-E ? Emissao de geracao vinculada ao lock (somente laboratorio)

Data: 2026-10-21. Base: `5e718e9`.

A API `issue_generation` nao aceita mais a indicacao booleana `lock_held=True`. Agora exige uma instancia `SupervisorLock` adquirida, com handle aberto, PID proprietario do processo atual e mesmo diretorio da base `supervisor_fence.sqlite3`. A transacao SQLite continua usando `BEGIN IMMEDIATE` e as geracoes antigas sao rejeitadas pela consulta de observacao.

Ensaios isolados: ausencia de lock, lock liberado, lock em conflito no mesmo processo, lock de outro diretorio e processo Windows independente em disputa; o concorrente so consegue emitir nova geracao depois da liberacao do lock. `python -m unittest discover -s tests -p test_incremental_*.py -q`: 311 testes aprovados.

Limites: verificacao de posse e identidade do handle no processo atual nao e certificado de fencing global nem evita modificacao de SQLite por escritor nao cooperativo. Nao ha worker, scheduler, deploy, backup real ou autorizacao para publicar geracao. Validar crash/restart e comportamento de processos reais antes de qualquer integracao.
