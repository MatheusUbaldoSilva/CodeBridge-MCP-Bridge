# RAG-LAB.04 — Atualização dos gates de publicação e probes

Data: 2026-10-18
Escopo: exclusivamente fixtures sintéticas descartáveis.

## Nova evidência

- 5b6f724: teste reproduziu sidecar Qdrant WAL tardio, criado durante gravação do relatório, após o hash inicial. Captura publicada indevidamente antes da correção. Guarda final imediatamente antes do os.rename rejeita sidecar Qdrant e SQLite principal, limpa staging.
- 00b5088: catálogo sintético e probe de handles tratavam storage.sqlite-wal/-shm/-journal internos de Qdrant como legíveis, ainda que sem autorizar cópia. Guardas de entrada e saída agora mantêm BLOCKED; teste com os três sufixos e os dois probes.

## Última regressão

382 PASS = 254 offline + 83 generation + 7 preflight + 38 incremental.
Commits auditados e publicados na branch rag-017-optimized-inference-after-candidate.

## Limitação essencial

Uma checagem de arquivos antes de renomear não prova ausência de atividade depois dessa checagem. A janela TOCTOU não pode ser encerrada universalmente por amostragens pontuais. Falta observador externo real, inventário independente de processos e mappings, bloqueio coordenado de novos writers e autorização específica de manutenção. A RAG-LAB.05 de produção continua bloqueada.

copy_authorized=false
all_handles_closed=false
production_quiescence_proven=false
production_backup=BLOCKED
