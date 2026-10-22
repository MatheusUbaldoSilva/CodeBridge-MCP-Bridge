# RAG V1.03 P8 — Descoberta e aprovacao pre-fila, somente leitura

Data: 2026-10-21
Branch: rag-017-optimized-inference-after-candidate
Escopo: progresso real na integracao futura do scheduler, sem inicio de worker.

## Alteracoes aprovadas

- rag/runtime/incremental_installed_change_discovery.py:
  compara as fontes indexadas da geracao publica com o checkout Git atual,
  usando o mesmo SHA textual do indexador. Revalida ponteiro antes de aceitar
  a fotografia e preserva o indice em modo somente leitura.
- rag/runtime/incremental_explicit_source_preview.py:
  confere somente fontes individuais explicitamente aprovadas; exige
  timestamp de observacao, debounce, Git HEAD, fonte commitada e SHA.
  Confere que cada caminho ainda nao consta do manifesto da geracao publica.
  Nao cria fila ou job nem concede permissao de publicacao.
- rag/runtime/incremental_installed_change_discovery_cli.py:
  diagnostico real; opcional --approve-source CAMINHO, junto de
  --changed-at-epoch TIMESTAMP e --debounce-seconds SEGUNDOS.
  Retorna codigo 2 para origem suja, fonte ausente, debounce incompleto,
  snapshot alterado ou outro bloqueio.
- O manifesto publico e validado segundo o contrato oficial de schema,
  contagem e digest rechecado ao final do preview.
- Testes de fontes ausentes, conteudo modificado, manifesto invalido,
  troca de ponteiro, escopo/tempo invalidos e Git nao commitado.

## Resultado real conferido

- CodeBridge MCP READY; indice publico v1_delta_1ae1d01ea84f4e
- 211 documentos, 8774 chunks.
- 211 fontes do manifesto verificadas; zero fontes alteradas ou ausentes.
- Exemplo real read-only: rag/runtime/incremental_explicit_source_preview.py,
  apos commit e passagem do debounce, classificado ELIGIBLE_FOR_DURABLE_QUEUE.
  Esse estado NAO significa job enfileirado: queued=false.
- 41 testes de regressao do escopo P8 + P7 + fila aprovados.

## Limites de ativacao

- A fila de producao jobs/incremental_jobs.sqlite3 ainda NAO existe.
- Worker, watcher, agendamento automatico e publicacao incremental autonomos nao foram iniciados.
- Inicializacao de fila foi anteriormente bloqueada pela ferramenta; nao
  contornar o bloqueio por outro canal.
- A descoberta de novas fontes e intencionalmente somente por paths
  explicitamente aprovados; nao faz varredura de arquivos nao autorizados.
- O legado com rollback e a geracao publica permanecem preservados.
- Nao declarar V1 concluida ate que fila e job unico real sejam validados.

## Commits

260bb73: descoberta de fontes indexadas.
4fd2dc6: preview individual de fonte aprovada.
be4a7fd: CLI de diagnostico e preview.
4939c18: saida bloqueada para candidatos nao prontos.
0f4dd96: schema de manifesto publico.
da4b04b: revalidacao de digest/contagem do manifesto.

Proxima fase: integrar ciclo limitado e autorizado do worker com lock,
fence, lease e rollback; exigir prova do job sem ativar geracao por inferencia.
