# RAG V1.03 — P9-A | Contrato de fila e worker offline isolado

Data: 2026-10-21
Branch oficial: rag-017-optimized-inference-after-candidate
Escopo: integracao entre pre-fila e fila persistente existente, sem ativacao automatica no Windows instalado.

## Implementacao

- Exige o caminho EXATO para a fila instalada:
  CodeBridge/rag/jobs/incremental_jobs.sqlite3.
  Qualquer pasta aninhada, inclusive com nome jobs, e rejeitada.
- Corrige a deteccao de fontes que JA estao no manifesto, mas cujo conteudo
  mudou no Git: REINDEX_CHANGED. Fontes novas recebem INDEX_NEW.
- Arquivos ausentes na fonte indexada nao sao agendados automaticamente.
- Gera identidade deterministica do job a partir do contrato existente:
  SHA256(codebridge + separadores NUL + path + commit + SHA fonte).
- A intencao e sempre ADVISORY_QUEUE_INTENTS_PREPARED, com
  must_revalidate_at_enqueue=true e queued=false.
- A CLI unificada aceita --show-queue-intent somente com paths explicitos.
- O contrato exige commit Git, SHA de fonte, aprovacao individual e debounce.
  Nao ha side effects no indice RAG pela etapa de preview.

## Evidencia de teste

1. Sintetico com fonte nova:
   Git -> preview -> intencao -> enqueue SQLite TEMP;
   job_id igual ao hash calculado pela intencao.
2. Sintetico com fonte reindexada:
   manifesto da versao anterior -> alteracao Git commitada -> freshness DRIFT
   -> REINDEX_CHANGED -> intencao -> enqueue isolado -> claim atomico unico.
   Segunda reclamacao retorna QUEUE_EMPTY.
3. Invalida preview antigo: fonte modificada sem commit retorna
   SOURCE_NOT_COMMITTED e nao cria SQLite; HEAD substituido retorna
   COMMIT_SUPERSEDED e tambem nao cria banco.
4. Modelo local instalado:
   teste especifico test_real_code_staging_receipt_without_publication PASS.
   Gerou staging offline/recibo com Jina, sem alteracao do indice publico.
5. Publico CodeBridge antes e depois:
   generation=v1_delta_1ae1d01ea84f4e, 211 documentos e 8774 chunks,
   estado READY, nenhuma geracao nova publicada.

## Restricoes

- A fila real instalada permanece ausente; criacao foi bloqueada
  pela ferramenta na etapa anterior. Nao utilizar outra ferramenta para
  contornar esse bloqueio.
- Nenhum scheduler continuo, watcher ou publicacao automatica foi ativado.
- O teste do worker usa uma fila TEMP sintetica e staging isolado:
  NAO equivale a processamento real de producao.
- O arquivo local nao commitado incremental_installed_queue_init.py
  continua um rascunho, separado dos commits.
- O RAG publico e os arquivos do usuario nao foram alterados.

## Commits da P9-A

- 0bc85c3: caminho exato da fila instalada.
- 0656a46: detecta REINDEX_CHANGED.
- d31e919: contrato consultivo de intencao e CLI.
- 3ebbdf1: teste nova fonte ao SQLite sintetico.
- 65294b6: fonte alterada e reclamacao atomica sintetica.
- 4d6eb64: rejeicao por dirty Git e superseded HEAD.

## Proxima etapa P9-B

Provar o bootstrap legitimo da fila instalada quando permitido, o ciclo
supervisionado unico com lock + fence duravel + lease, recuperacao e rollback.
Depois validar um unico arquivo de teste aprovado no CodeBridge real.
Nao declarar RAG V1 concluida antes disso.
