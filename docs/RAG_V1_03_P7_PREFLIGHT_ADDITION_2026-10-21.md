# RAG V1.03 — P7 adicao: gate instalado e diagnostico de prontidao

Data: 2026-10-21
Base: e25b68b
Ultimo incremento: 03dd41d

## Implementacao desta rodada

- Publico ativo continua v1_delta_1ae1d01ea84f4e: 211 documentos / 8774 chunks.
- Preflight read-only recusa ponteiro publico invalido ou transicao pendente.
- Inspecao instalada exige fence duravel em jobs/supervisor_fence.sqlite3 e geracao inteira positiva.
- Gate acumula TODOS os bloqueios, mesmo com fence ausente.
- Releitura do ponteiro e journal apos o diagnostico invalida estado caso ocorra mudanca concorrente.
- CLI possui --require-ready e sai com codigo 2 quando precondicoes estao bloqueadas; sem flag continua diagnostico comum.
- Nenhuma interface confunde PREREQUISITES_OBSERVED_ONLY com autorizacao de scheduler: activation_authorized permanece falso.
- 39 testes focados de diagnostico, fila, ponteiro e fence aprovados.

## Bloqueios reais ainda observados

QUEUE_DISABLED
WORKER_DISABLED
SCHEDULER_DISABLED
SOURCE_APPROVAL_REQUIRED
INSTALLED_RUNTIME_UNVERIFIED
RECOVERY_UNVERIFIED
PUBLIC_INDEX_INTEGRITY_UNVERIFIED
QUEUE_STORE_ABSENT
INSTALLED_DURABLE_FENCE_REQUIRED

Nao existe fila instalada em AppData/Local/CodeBridge/rag/jobs/incremental_jobs.sqlite3.
Nao foi disparado scheduler ou worker de producao.
A tentativa anterior de criar fila foi bloqueada pela ferramenta. O rascunho local
rag/runtime/incremental_installed_queue_init.py NAO FOI PUBLICADO e nao deve ser
confundido com funcionalidade pronta.

## Decisao

Fechar somente a subetapa de preflight read-only, nao o scheduler autonomo.
Proxima entrega executavel exige operacoes de fila autorizadas pela superficie
da ferramenta, vinculacao atomica de lock/fence/lease e validacao de job unico.
Preservar o indice publico e seu rollback ja comprovado.
