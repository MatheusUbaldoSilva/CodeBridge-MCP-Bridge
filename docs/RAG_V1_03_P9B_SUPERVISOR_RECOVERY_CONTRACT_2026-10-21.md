# RAG V1.03 — P9-B: provas de recuperacao e limites de ativacao

Data: 2026-10-21
Branch: rag-017-optimized-inference-after-candidate
Status: EM ANDAMENTO. NAO houve bootstrap da fila instalada nem ativacao do scheduler.

## Evidencias da etapa

- Tests/test_incremental_p9b_synthetic_installed_readiness.py:
  fila SQLite v2 + fence duravel + OS lock em TemporaryDirectory.
  Preflight aceita os prerequisitos sinteticos como OBSERVED_ONLY,
  nunca ativa worker; rejeita fence obsoleto, schema invalido e journal pendente.
- tests/test_incremental_p9b_lease_crash_recovery.py:
  job com lease expirado pode ser reclamado por nova tentativa;
  lease token antigo nao consegue renovar, alterar ou recuperar a reserva;
  falha limitada por max_attempts; restart gera fence superior e invalida antigo.
- rag/runtime/incremental_job_prequeue.py:
  timestamps e debounce validam tipo numerico e finitude;
  NaN, infinito, texto e bool sao recusados antes da elegibilidade.
- rag/runtime/incremental_job_queue.py:
  validacao de tempo/politica antes de INSERT, claim, retry, renovacao
  e acknowledge; recusas sao fail-closed.
- rag/runtime/incremental_installed_claim_gate.py:
  inspecao somente leitura exige posse REAL de supervisor.lock no caminho
  instalado correto, fence atual, preflight e aprovacao de fontes.
  Retorna CLAIM_PREREQUISITES_OBSERVED_ONLY. Nunca reclama um job.
- Nenhuma rotina desta etapa faz publicacao, atualiza indice ou inicia servico.

## Auditoria

- 104 testes focados de P9-A, P9-B, fila, staging offline e supervisor PASS.
- HEAD e upstream conferidos iguais no Git oficial.
- MCP RAG publico READY, geracao v1_delta_1ae1d01ea84f4e,
  211 documentos, 8774 chunks.
- Historicos nao relacionados preservados sem staging:
  benchmarks/rag017_code_only_extended_smoke.json (modified),
  docs/RAG_017_J_VM_ROLLBACK_RUNBOOK_2026-10-10.md (untracked),
  rag/runtime/incremental_installed_queue_init.py (untracked).

## Pendencias reais

1. O arquivo instalado jobs/incremental_jobs.sqlite3 ainda NAO existe.
   A tentativa de inicializacao anterior foi bloqueada pela ferramenta.
   Nao tentar contornar essa restricao por Remote Desktop ou outro caminho.
2. A sequencia pronta-em-laboratorio precisa de autorizacao/execucao
   permitida e comprovacao na instalacao real, sem criar novo servico.
3. Ainda falta chamar worker supervisionado de forma unica e limitada,
   com verificacao lock+fence imediatamente antes de claim, renovacao,
   fail/retry, staging e ack.
4. Ainda falta demonstrar deteccao automatica de alteracoes, restart
   e eventual publicacao com rollback na instalacao real.
5. Fechar Git + patchnotes/handoff de P9-B somente depois desses gates.

## Commits desta rodada

- c927825: readiness de fila e fence instalados, sintetico.
- 737599e: recuperacao do lease e rejeicao do worker antigo.
- beaf0ce: restart real do lock/fence em teste isolado.
- 4e67464: validacao de tempos de evento antes de gravar SQLite.
- 350f437: guardas numericas de claim/lease/falha/ack.
- ab82fda: ownership gate do lock e fence antes de claim.

Esta nota registra progresso tecnico, nao concede autorizacao de ativacao.
