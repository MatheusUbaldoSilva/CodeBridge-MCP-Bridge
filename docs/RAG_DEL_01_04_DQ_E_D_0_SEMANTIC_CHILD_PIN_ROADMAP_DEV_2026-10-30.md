# RAG-DEL-01.04-DQ-E-D-0 — Plano para handoff semantico pinado (DEV)

Status: PLANEJADO; nenhuma modificacao no executor semantico real autorizada por este documento. Base: dev-local 838b1f4. Progresso DQ-E-C foi uma auditoria AST source-only, NAO uma implementacao de inferencia protegida.

## Problemas a resolver

1. semantic_isolated_project hoje adquire semantic exclusive internamente por ate 100 s de retry; envolvimento externo com semantic exclusive causaria risco de dupla aquisicao/reentrancia.
2. O filho isolated_project_worker abre novamente resolve_isolated_project(data["project_id"]), sem receber comprovante da mesma geracao e manifesto mantidos pelo pai. A verificacao de hashes isolada feita pelo child nao e contrato parent-child pinado.
3. Nao introduzir catalog mutex no processo child se o pai mantiver o mesmo mutex enquanto aguarda o subprocesso. Manter generation(shared) -> semantic(exclusive) -> catalog e nenhuma inversao. A renovacao de lease/heartbeat da fila deve continuar livre.

## DQ-E-D-1 — Contrato e testes primeiro

- Definir immutable PrivateReadPinEnvelopeV1: project_id, generation_id, source_revision, manifest_sha256, sqlite_sha256, catalog_revision/fingerprint e nonce por requisicao. Nenhum caminho arbitrario vindo de usuario.
- Usar fixtures TEMP com duas geracoes e hashes distintos. O child deve rejeitar qualquer divergencia antes de abrir SQLite/Qdrant.
- Exigir prova de que writer cutover nao acontece durante sessao de inferencia.

## DQ-E-D-2 — Executor semantico nao reentrante

- Extrair do wrapper legado uma funcao executora que exija semantic lock JA detido e nao o adquira outra vez.
- Manter a entrada legada atual com lock proprio para clientes sem sessao externa; testar compatibilidade.
- Nenhum lock novo pode ser adquirido pelo child dentro de um catalog mutex mantido pelo pai.

## DQ-E-D-3 — IPC e worker

- Child recebe envelope pinado e valida identidade, allowlist de geracao, catalogo, index/manifest/provenance; nao re-resolver a geracao por ID desacompanhado do envelope.
- Rejeitar mismatch, falta de hash, arquivo trocado, killed subprocess, timeout e tentativa de acesso a projeto alheio.
- Evitar subprocessos modelo pesado na primeira prova: worker fake com sauda JSON sintética.

## DQ-E-D-4 — Concorrencia e recuperacao

- Processos Win32 reais: leitor pinned vs writer exclusive, semantic livre/ocupado, lock timeout, cancelamento, crash e reabertura.
- Verificar que um journal anterior mesmo ROLLED_BACK continua bloqueando leitura no guard atual ate reconciliacao autorizada por procedimento separado.
- Regressao completa RAG-DEL/RAG-AUTO e auditoria diff/commit seletivo.

## DQ-E-D-5 — Gates para etapa instalada

- Somente apos DEV passar, disponibilizar probe MCP realmente carregado e atestar GUI/child; testes anteriores de AST/snapshot nao bastam.
- Nao alterar Stable/candidato, nao executar exclusao real, nao alterar fila/indices reais, nao publicar GitHub sem autorizacao separada.