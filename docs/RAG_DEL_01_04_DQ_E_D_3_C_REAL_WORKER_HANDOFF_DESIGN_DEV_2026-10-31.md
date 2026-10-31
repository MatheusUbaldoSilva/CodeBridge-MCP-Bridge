# RAG-DEL-01.04-DQ-E-D-3C — Projeto de handoff para worker real (NAO IMPLEMENTADO)

Status: design DEV, fase PLANEJADA. Base: 2fb4d76. Nao afirma homologacao do worker real, nao autoriza delete.

## Situacao comprovada
- A rota semantic_isolated_project() no DEV continua com wrapper legado que adquire semantic exclusive, com executor subprocess isolado do lock em _invoke_isolated_semantic_subprocess_unlocked.
- A DQ-E-D-1...3B criou protocolo strict em laboratorio com envelope de geracao, request_digest, nonce, pedido e resposta, fake worker e testes Win32. Ele NAO abre modelos/Qdrant reais.
- isolated_project_worker.py de producao no DEV ainda resolve projeto por project_id e nao recebe esse envelope. O MDC/MCP conectado nao expoe generation_probe; GUI Stable/candidato nao possuem public pinned helper.

## DQ-E-D-3C-1 — Identidade e contrato
1. Manter o fluxo legado existente com seu lock, sem mudanca implicita na busca public/private atual.
2. Adicionar caminho explicitamente opt-in DEV para worker real que exija schema de IPC versionado, project_id, generation_id, source_revision, hashes SQLite e manifesto, catalog fingerprint e nonce vinculado a uma sessao ativa.
3. Child deve resolver APENAS geracao permitida em workspace aprovado, sem caminhos arbitrarios da consulta. Conferir todos os hashes, invariantes RAG-DEL e origem; reler antes/depois da inferencia.
4. Diferenciar REQUEST_SHA256 (correlacao, sem autenticar) da prova real de liveness e seguranca do parent. Nunca elevar hash/nonce a credencial de exclusao.

## DQ-E-D-3C-2 — Lock e tempo
1. Parent retém generation(shared) -> semantic(exclusive) -> catalog mutex durante todo o IPC e avalia a saida antes de soltar locks. Child nao readquire semantic ou catalog mutex que o parent reteve.
2. Definir timeout fim-a-fim, cancelamento do subprocesso e invariantes de saida apos falha. Nao aguardar semantic enquanto segura queue BEGIN IMMEDIATE, evitando heartbeat deadlock.
3. Separar worker legado com resolucao atual do novo modo pinado; prevenir fallback silencioso para indice/geracao diferente.

## DQ-E-D-3C-3 — Testes antes de ativar
- SQLite/Qdrant e manifests sinteticos em TEMP, duas geracoes, mismatched hashes, symlinks, path escape, source revision stale, catalog CAS concorrente, child crash, timeout, worker pendurado.
- Testes do subprocesso real com dependencias stubbed no DEV para nao carregar modelos pesados; garantir zero chamadas de Qdrant em falha de preflight.
- Revisar Unicode/JSON, tamanho maximo, duplicidade de nonce, codigos de erro estruturados, audit trail e saida que nunca concede autorizacao operacional.
- Regressao RAG-DEL/RAG-AUTO, Git diff/check, checkpoint, commit; posterior atestacao instalada separada antes de qualquer piloto.

## Bloqueios adicionais
- Depois de ROLLED_BACK, o journal historico ainda impede leitor com guard atual. Reconciliacao/arquivamento auditado permanece pendente e nao deve apagar evidencias.
- Fila real READY_FOR_REVIEW pendente, gate de exclusao permanece False.
- Sem push Github, instalacao Stable/candidato, ativacao real, reset de arquivos do usuario ou indice operacional.