# RAG V1.03-J ? Gate do scheduler com validacao opcional de geracao

Data: 2026-10-21. Base: `1e5ff79`.

O gate apenas diagnostico `assess_autonomous_worker_gate` aceita de forma opcional a base `durable_store` e `expected_durable_generation`. Quando um destes argumentos e informado sem o outro, ou a geracao nao corresponde a base SQLite, retorna bloqueio `DURABLE_FENCE_UNVERIFIED`. A observacao correta remove apenas este bloqueador especifico sem autorizar ativacao ou publicacao.

Nao adquire lock, nao altera arquivos e nao ativa worker/scheduler. A validade da geracao no instante da consulta nao garante validade posterior ou seguranca para escrever; producao continua bloqueada.
