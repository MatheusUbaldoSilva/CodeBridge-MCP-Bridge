# RAG V1.03 — P7: reforco de preflight do scheduler instalado

Data: 2026-10-21
Branch: rag-017-optimized-inference-after-candidate

## Escopo implementado

- Diagnostico instalado recusa ponteiro publico invalido.
- O fence duravel do supervisor precisa ter exatamente o caminho oficial:
  AppData/Local/CodeBridge/rag/jobs/supervisor_fence.sqlite3.
- A geracao duravel precisa ser inteiro positivo; booleanos nao sao aceitos.
- O diagnostico acumula bloqueios, sem esconder fila ausente/worker desligado.
- Ponteiro e journal sao reobservados apos a inspecao; se houver mudanca durante o preflight, o resultado vira BLOCKED.
- Nenhuma dessas verificacoes inicia worker, cria fila, altera geracao ou publica embeddings.

## Prova real

- CodeBridge MCP 2.0.11-prealpha READY.
- Geracao publica: v1_delta_1ae1d01ea84f4e; 211 documentos; 8774 chunks.
- CLI retorna AUTONOMOUS_SCHEDULING_BLOCKED.
- Fila jobs/incremental_jobs.sqlite3 ausente.
- Faltam ativacao de fila/worker/scheduler, aprovacao de fonte, prova do runtime, recuperacao, integridade e fence duravel.
- 36 testes de regressao de fila, ponteiro, gate e fence passaram.
- RAG publico nao modificado.

## Limites e proxima etapa

- Codigo legado da fila persistente e do worker offline existe, mas nao esta conectado a um scheduler instalado.
- Um arquivo nao versionado de inicializacao da fila foi gerado em etapa anterior e nao equivale a funcionalidade instalada.
- A tentativa de criacao real da fila foi bloqueada por seguranca da ferramenta. Nao contornar o bloqueio por ferramentas alternativas.
- Integracao automatica so podera ser considerada concluida apos job aprovado, reclamacao atomica, fence/lock/lease consistentes,
  staging, validacao, publicacao supervisionada e rollback real.
- Manter os arquivos historicos do working tree inalterados.

Commits:
- cc33fa1 recusa ponteiro publico invalido.
- 3daddf0 exige fence instalado.
- 3ed677a acumula bloqueios.
- 0d127bc verifica estabilidade de ponteiro.
