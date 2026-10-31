RAG-DEL-01 — Patch notes DEV, continuidade 2026-10-30

Entregas: a531903 planejamento de recuperacao somente leitura; 2eb9a32 integridade SHA256 de journal; 5768ac0 concorrencia multiprocessos e rollback em outro processo; 35c6d77 preflight de catalogo privado; 95d1f8c verificacao de backup; 7e2ad96 contrato de revisao; cd8d110 hashes imutaveis; 3873887 invalidacao de confirmacao obsoleta; e63c617 snapshot de fontes; 2bfbb37 prova de snapshot obrigatoria na revisao; 47deb7c tamanho do arquivo; 4c94d03 prova de snapshot obrigatoria no gate de transicao.

Validacoes: RAG-DEL 189 testes (187 PASS, 2 SKIP); RAG-AUTO 241 testes (236 PASS, 5 SKIP); MCP 5 PASS. Total 435, zero falhas nas suites separadas. Snapshot real newworldpvp verificado somente leitura: 435 arquivos, 4.358.269 bytes, hash e tamanho compativeis.

Continuam bloqueadas: exclusao real, troca operacional do catalogo e ativacao da geracao. Faltam fencing de workers em producao, verificacao final do candidato fechado sob lock, rollback e homologacao de falhas. Sem alteracao na Stable, no indice publico ou nas fontes reais; sem push.

RAG-DEL-01.04-J (DEV): journals terminais ROLLED_BACK passam a exigir identidade, schema, backup existente e SHA-256 consistente antes de autorizar nova transacao de laboratorio. Novos testes em tests/test_rag_del_01_04_j_terminal_journal.py: 7 PASS. Suite RAG-DEL no runtime dev: 196 executados (194 PASS, 2 SKIP), zero falhas. Nao habilita exclusao real nem ativacao operacional; sem push.

RAG-DEL-01.04-K (DEV): segunda validacao do recibo da geracao candidata enquanto o mutex do catalogo estiver adquirido, imediatamente antes de qualquer backup/journal. Se a geracao se tornar invalida entre as duas verificacoes, troca e journal sao abortados no laboratorio. Testes RAG-DEL: 199 (197 PASS, 2 SKIP). RAG-AUTO, sem o caso MCP que exige runtime separado: 241 (236 PASS, 5 SKIP). Sem ativacao operacional.

RAG-DEL-01.04-L (DEV): reauditoria de proveniencia da candidata dentro da secao critica de catalogo no laboratorio, comparando linhagem, snapshot, manifesto, contagem de sobreviventes e flags de nao ativacao. Alteracao de prova bloqueia a transacao. RAG-DEL: 201 testes (199 PASS, 2 SKIP), sem falhas. Sem worker fencing operacional, sem exclusao real ou push.

RAG-DEL-01.04-M (DEV): testes ponta a ponta em catalogo temporario validam integracao da reauditoria sob mutex: divergencia de manifesto causa abort sem gravar journal/backup, e provas estaveis permitem troca e rollback mantendo projeto vizinho e ponteiro publico. Suite RAG-DEL: 203 testes (201 PASS, 2 SKIP). Teste real com workers ainda pendente; ativacao permanece bloqueada.

RAG-DEL-01.04-N (DEV): detecta backups orfaos rag-del-*.previous.json sem journal correspondente no preflight e antes da troca do catalogo temporario; falha de fechamento seguro sem gravar novo journal. Testes: 3 novos aprovados, RAG-DEL 206 executados (204 PASS, 2 SKIP), zero falhas. Nenhum catalogo real alterado.

RAG-DEL-01.04-O (auditoria DEV, sem codigo operacional): o mecanismo production_generation_lock possui canais independentes generation e semantic. production_generation_transition protege o cutover com generation exclusivo, enquanto auto_index_incremental_fenced utiliza semantic exclusivo e lease do supervisor. Logo, um lock generation isolado NAO prova quiescencia de todos os escritores semanticos. Antes da exclusao real e necessario definir ordem de aquisicao de ambos os canais, evitar deadlock, drenar workers, verificar leases, bloquear novos jobs e testar rollback operacional em isolamento. A troca real permanece proibida.

RAG-DEL-01.04-P/Q/R (DEV): barreira SQLite BEGIN IMMEDIATE em fila temporaria do supervisor, locks injetados ordenados fila -> generation -> semantic, rejeicao de leases (inclusive expiradas) e jobs pendentes, prova de concorrencia multiprocessos, swap/rollback isolado e simulacoes de crash real (os._exit) com reconciliacao explicita. Testes RAG-DEL 222 (220 PASS, 2 SKIP), zero falhas. Nao autoriza nenhuma ativacao real.

RAG-DEL-01.04-S (DEV): 2 testes com LockFileEx efetivo do CodeBridge, ambos canais sob root sintetico mockado, cobrindo exclusao de outro processo e desalocacao parcial ao falhar no segundo lock. Somente scratch, nao altera root de producao nem libera exclusao real.

RAG-DEL-01.04-T (DEV): revisao somente leitura do supervisor AUTO em SQLite existente (mode=ro, query_only), sem criar banco ou alterar leases. Detecta fila ausente, schema invalido, integridade, lease ativa ou expirada, e jobs nao terminais. Resultado observado quieto continua activation_authorized=False e queue_barrier_held=False. Testes: 11 novos PASS; RAG-DEL 235 testes (233 PASS, 2 SKIP); RAG-AUTO 241 testes (236 PASS, 5 SKIP), sem falhas em suites executadas.

RAG-DEL-01.04-U/V (DEV): adaptador de transicao provenance-gated de laboratorio exige barreira da fila + dois locks antes de chamar swap; revisao previa READ_ONLY do supervisor agora carrega hash da identidade do caminho, e o adaptador confere flags imutaveis e a geracao singleton dentro da barreira. Mudanca de geracao entre revisao e swap exige revisar novamente. 12 testes de adapter aprovados; suite RAG-DEL 247 (245 PASS, 2 SKIP), 0 falhas. Ativacao e exclusao operacionais continuam negadas; nao ha promocao remota.

RAG-DEL-01.04-W (DEV): regressao valida que READY_FOR_REVIEW, apesar de nao manter lease ativo, continua bloqueado por nao ser estado terminal resolvido de fila. Auditoria real somente leitura confirma necessidade de reconciliar/revisar estados antes de homologacao, sem revelar job IDs nem alterar fila. Nenhuma operacao mutavel foi realizada.

RAG-DEL-01.04-Y/Z (DEV): marcador duravel auto_deletion_reservation_freeze (FROZEN/OPEN, token, generation) criado SOMENTE em banco de laboratorio. reserve_index_supervisor consulta marcador na mesma transacao BEGIN IMMEDIATE antes da reserva, falhando fechado se congelado/malformado. Testes de persistencia apos crash e concorrencia multiprocessos; workers existentes nao sao interrompidos. RAG-DEL 264/262 PASS/2 SKIP e RAG-AUTO 241/236 PASS/5 SKIP, 0 falhas. Nao houve alteracao Stable ou escrita de fila real.

RAG-DEL-01.04-AA (DEV): a revisao READ_ONLY do supervisor reporta apenas ativo e generation do freeze. O adapter provenance gated exige freeze ativo e writer-fence valida generation sob BEGIN IMMEDIATE; thaw/re-freeze invalida revisoes anteriores. Testes RAG-DEL: 266 (264 PASS, 2 SKIP); RAG-AUTO (apos Y/Z): 241 (236 PASS, 5 SKIP). Nenhuma exclusao ou ativacao real.


RAG-DEL-01.04-BB (DEV): teste integrado real de laboratorio
freeze->review->locks->catalog CAS->rollback->thaw (3 casos) passou com
auditoria de proveniencia/geracao isolada por mocks; corrigida a ordem de locks
para generation -> semantic -> queue para evitar espera circular entre
semantic worker e heartbeat SQLite. Novo teste verifica que BEGIN IMMEDIATE
do worker continua disponivel enquanto a transicao espera semantic.
Sem alteracao de indice real nem autorizacao de exclusao.

RAG-DEL-01.04-DE (DEV): auto_index_worker._public_generation passa a usar production_generation_lock shared para leitura do ponteiro, com fail-closed para journal pendente, symlink, ponteiro invalido e lock Win32 ocupado. Testes multiprocessos inteiramente scratch. RAG-DEL 276 (274 PASS, 2 SKIP), RAG-AUTO non-MCP 241 (236 PASS, 5 SKIP), zero falhas; sem push nem Stable.

RAG-DEL-01.04-DF (DEV): o diagnostico read-only do scheduler incremental agora exige generation shared LockFileEx durante inspeção e, sob exclusividade concorrente, retorna PUBLIC_POINTER_BUSY sem fazer leitura insegura. 4 novos testes multi-processos scratch + 5 testes anteriores do agendador passaram. Nao autoriza schedule, cutover, nem exclusao real.

RAG-DEL-01.04-DG (DEV): auditoria read-only de lease (NONE/ACTIVE/EXPIRED_RECONCILIATION_REQUIRED/MALFORMED) e teste de recuperação real de job sintetico sob freeze. Expiracao nao autoriza exclusao, recuperacao requer operador e deixa job QUEUED bloqueado pelo freeze. Regressoes: RAG-DEL 286 (284 PASS/2 SKIP), RAG-AUTO non-MCP 241 (236 PASS/5 SKIP), sem falhas. Nenhum lease real foi alterado.

RAG-DEL-01.04-DH (DEV): testes multiprocessos reais com Win32 semantic exclusivo, heartbeat SQLite concorrente e crash via terminate. A fila permanece disponivel durante espera pelo lock; morte do processo nao limpa lease persistida nem desbloqueia exclusao. Somente fixtures em TEMP, sem alteracao de RAG real.

RAG-DEL-01.04-DI (DEV): production_generation_read._read_pointer rejeita symlink/junction do ponteiro. Testes em root temp, mock deterministico de redirecionamento aprovado e criacao real de symlink dispensada por WinError 1314. RAG-DEL 291 (288 PASS, 3 SKIP), generation journal 14 PASS, P3 16 PASS; sem ativacao operacional.

RAG-DEL-01.04-DJ (DEV): novo inventario publico SQLite read-only sob production_generation_read() com pin de geracao na consulta inteira; 5 testes Win32/temp passaram, sem misturar projetos privados. Auditoria aponta que public search/context do bridge MCP ja usa pin, porem a GUI documents ainda faz leitura direta (arquivo preexistente sujo PRESERVADO). Novo helper nao conectado a GUI; nenhum uso operacional.

RAG-DEL-01.04-DL (DEV): interface documents/codebridge usa inventario pinado DJ e preserva list[dict] sem fallback ao SQLite legado. Commit seletivo do ramo GUI (somente 8 linhas; diff preexistente intocado). Seis testes GUI scratch incluindo E2E com LockFileEx; teste smoke da quarta pagina corrigido segundo a base HEAD existente. Stable, indice real e exclusao sem alteracao.

RAG-DEL-01.04-DM (DEV): helper NOVO e somente laboratorial para inventario privado com _catalog_mutex, fingerprint SQLite, bloqueio de journals e namespaces segregados; sete testes com subprocesso/mutex reais em TemporaryDirectory. Nenhuma integracao GUI privada ou exclusao real foi habilitada.

RAG-DEL-01.04-DN (DEV): 3 testes Qt offscreen de erro de leitura com generation busy/catalago ocupado e isolamento na troca de projeto; publica nao libera selecao de exclusao. Sem alteracao adicional da GUI, Stable ou index real.

RAG-DEL-01.04-DO (DEV): auditada via fonte a rotina MCP codebridge_rag_generation_probe, disponivel no mcp_server.py mas nao exportada pela conexao CodeBridge atual; tres testes AST/mocks garantem read_only, writer bloqueado e safe_to_activate=False. Nao equivale a prova do processo MCP instalado e nao altera indice real.

RAG-DEL-01.04-DQ-B (DEV): novo bounded_catalog_mutex_lab somente TEMP com timeout nao bloqueante e identidade de lock conferida, usado no inventario DM. 325 RAG-DEL (321 PASS/4 SKIP), 241 RAG-AUTO non-MCP (236 PASS/5 SKIP), zero falhas; sem integracao operacional.

RAG-DEL-01.04-DQ-C-A (DEV): sessao composta TEMP-only generation(shared)->semantic(exclusive opcional)->catalog bounded, pin de hashes SQLite/manifesto durante leitura, callback semantico sintetico de uso unico e invalidado apos fechamento. 9 testes novos PASS; RAG-DEL 334 (330 PASS/4 SKIP), RAG-AUTO 241 (236 PASS/5 SKIP), sem falhas. Integracao real reservada a DQ-C-B.

RAG-DEL-01.04-DQ-C-B (DEV): testes dos servicos reais search_context/get_context com SQLite privado FTS5 temporario sob sessao composta DQ-C-A, isolamento de namespace e executor semantico sintetico sem segundo lock. 3 testes PASS; RAG-DEL 337 (333 PASS/4 SKIP), RAG-AUTO 241 (236 PASS/5 SKIP). Nenhuma integracao operacional.

RAG-DEL-01.04-DQ-D-A (DEV): testes Windows multiprocessos TEMP comprovam que morte do leitor libera generation/semantic/catalog locks e journal pendente permanece como bloqueio de leitura; fixture SQLite fecha handle explicitamente. RAG-DEL 339 (335 PASS/4 SKIP), RAG-AUTO 241 (236 PASS/5 SKIP), zero falhas. Sem recovery operacional.

RAG-DEL-01.04-DQ-D-B (DEV): concorrencia Win32 entre leitor privado pinado e writer fence real, CAS stale recusado, queue BEGIN IMMEDIATE bloqueia concorrencia, rollback idempotente de catalogo sintetico e pointer preservado. Journal historico continua bloqueando reader ate reconciliacao explicitamente auditada. RAG-DEL 342 (338 PASS/4 SKIP), RAG-AUTO 241 (236 PASS/5 SKIP), zero falhas. Nao operacional.
RAG-DEL-01.04-DQ-E-A (DEV): preflight source-only de atestacao MCP/GUI/worker/queue sem autorizacao operacional; probe registrado no codigo DEV ainda nao exposto no MCP conectado 2.0.11-prealpha. RAG-DEL 346 (342 PASS/4 SKIP), RAG-AUTO 241 (236 PASS/5 SKIP), zero falhas.
RAG-DEL-01.04-DQ-E-B (DEV): comparador source-only de snapshots GUI DEV/Stable/candidato com hashes e helper; Stable e candidato 570bb17 nao possuem leitor publico pinado, DEV possui; processo GUI iniciado antes da alteracao DEV e MCP conectado nao expoe probe. RAG-DEL 350 (346 PASS/4 SKIP), RAG-AUTO 241 (236 PASS/5 SKIP), zero falhas. Nao operacional.
DQ-E-C DEV: guard de contrato semantico source-only; parent adquire semantic e worker reabre catalogo. 353 RAG-DEL, 241 RAG-AUTO, 0 falhas. Worker real ainda nao atestado.
DQ-E-D-0: plano DEV para extrair executor semantic lock-already-held, envelope pinado no IPC child e testes Win32 sint�ticos antes de integrar. Apenas documentacao, nenhuma alteracao ao worker/GUI instalada.
DQ-E-D-1 DEV: envelope imutavel de geracao catalogo SQLite manifesto e nonce para worker de laboratorio TEMP; 10 testes novos PASS, cutover bloqueado durante child. RAG-DEL 363 (359PASS/4SKIP), RAG-AUTO 241 (236PASS/5SKIP), zero falhas; child nao atesta locks do parent e nao autoriza exclusao.
DQ-E-D-2 DEV: isolamento do helper sem lock para subprocesso semantico sob wrapper legado que ainda toma semantic uma vez; dispatcher TEMP exige sessao semantica e envelope pinado, sem segundo lock. 10 testes novos PASS; RAG-DEL 373 (369PASS/4SKIP), RAG-AUTO 241 (236PASS/5SKIP), zero falhas. Worker real permanece sem IPC pinado.
DQ-E-D-3A DEV: PinnedSemanticRequestV1 strict sobre IPC fake worker TEMP sem model/Qdrant com sha256 de requisicao, rotas, filtros, top_k. 6 testes novos PASS. RAG-DEL 379 (375PASS/4SKIP), RAG-AUTO 241 (236PASS/5SKIP), 0 falhas. Worker real nao integrado.
DQ-E-D-3B DEV: correlacao de resposta de worker fake (nonce, sha256 de request, projeto, geracao, rota) sob semantic lock ja detido; timeout, tamper e flags operacionais forjadas fail-closed. 7 testes novos PASS; RAG-DEL 386 (382PASS/4SKIP), RAG-AUTO 241 (236PASS/5SKIP), zero falhas. Nao e autenticacao/atestacao do child real.
DQ-E-D-3C DESIGN: real semantic worker still not bound to pinned IPC; design roadmap maps identity/allowed path, no parent-child reentrant lock, liveness, fail-closed fallback, crash/timeouts and installed attestation. Documentation only; no production activation.
DQ-E-D-3C-A (DEV): real isolated_project_worker entrypoint opt-in --pinned-scratch-only validates strict TEMP pinned semantic IPC, no model/Qdrant/index resolver, legacy unchanged. 7 new tests PASS; 393 RAG-DEL (389 PASS,4 SKIP), 241 RAG-AUTO (236 PASS,5 SKIP), zero failures. No operational attestation.
