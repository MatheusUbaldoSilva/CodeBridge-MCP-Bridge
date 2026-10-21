# RAG V1.03-K ? Fronteira real do agendamento autonomo

Data: 2026-10-21. Base: `1bc11a4`. Auditoria estatica de codigo, sem ativacao.

## Modulos observados

- `rag/runtime/incremental_job_prequeue.py` ? `assess_commit_index_event` valida escopo, commit e conteudo em modo somente leitura antes do enfileiramento.
- `rag/runtime/incremental_job_queue.py` ? fila persistente e aquisicao de jobs aprovados mediante gate.
- `rag/runtime/incremental_offline_worker.py` ? `process_offline_job_once` processa somente um job aprovado com heartbeat e staging; exige `queue_enabled=True`, `worker_enabled=True` e fontes aprovadas. Nao e um scheduler.
- `rag/runtime/incremental_scheduler_gate.py` ? `assess_autonomous_worker_gate` apenas diagnostica precondicoes e, opcionalmente, confere token duravel; `activation_authorized=False` e `safe_to_publish=False` invariantes.
- `rag/runtime/incremental_supervisor_lab_runner.py` ? runner de laboratorio com lock real, contador duravel opcional e callback inofensivo; nao e servico de producao.

## Limites e pendencias antes de ativacao real

1. Nao existe nesta trilha um loop autonomo de scheduler validado, nem integracao real entre o gate de leitura, a propriedade duravel do supervisor e a reclamacao de job.
2. Validar de maneira atomica/consistente token duravel, lock e direito de reclamar/confirmar um job; verificar novamente antes de qualquer efeito, evitando TOCTOU.
3. Isolar claramente lease por job de geracao de supervisor; os dois mecanismos nao sao equivalentes.
4. Testar restart, falha, cancelamento cooperativo, perdida de lock e dupla instancia contra fixtures antes de qualquer execucao instalada.
5. Autorizacao de publicacao e integridade do indice publico permanecem independentes deste gate.

## Decisao

Estado `GO-LIVE BLOCKED`. Worker e scheduler reais continuam desligados. Nenhum codigo existente foi ativado ou processo interrompido. Proximo incremento deve ser um contrato de preflight somente leitura com testes isolados e sem side effects; nao adicionar agendador automatico enquanto os bloqueios acima persistirem.
