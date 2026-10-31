# RAG-DEL-01.04-DQ-D-B — Concorrencia CAS, leitores e rollback Win32 (DEV)

## Resultado
Suite nova test_rag_del_01_04_dqdb_cas_rollback_race_lab.py usa exclusivamente TemporaryDirectory, SQLite e arquivos catalogo/ponteiro sinteticos.

Cenario 1: processo Windows leitor privado mantem generation(shared) -> semantic(exclusive) -> catalog. O escritor tenta generation(exclusive) pelo laboratory_writer_fence e recusa via ProductionGenerationBusy, sem journal, alteracao de catalogo ou ponteiro. Depois da liberacao do leitor, o escritor adquire generation(exclusive) -> semantic(exclusive) -> queue BEGIN IMMEDIATE -> catalog mutex, realiza laboratory_swap CAS, verifica preservacao de outro projeto e ponteiro publico, e executa rollback; o catalogo retorna ao hash original.

Cenario 2: durante o writer fence, outro processo tenta abrir o private_read_session_lab e recebe READER_BUSY; outro processo tenta BEGIN IMMEDIATE na fila sintetica e recebe QUEUE_BUSY. Depois que o fence sai, a leitura original volta a ser possivel.

Cenario 3: CAS com revision stale e recusado antes de criar journal; falha injetada apos troca gera journal PREPARED, bloqueia nova troca, e rollback explicito restaura catalogo original, verifica idempotencia ALREADY_ROLLED_BACK, nao modifica ponteiro publico nem projetos alheios.

Atencao: o bounded_catalog_mutex_lab recusa *qualquer* journal historico, mesmo estado ROLLED_BACK. Portanto novas leituras permanecem fail-closed apos rollback ate existir procedimento separado e auditado de reconciliacao/arquivamento dos journals. Nao remover journal automaticamente e nao afirmar recovery operacional concluido.

Regressoes: RAG-DEL 342 testes, 338 PASS, 4 SKIP. RAG-AUTO sem MCP 241 testes, 236 PASS, 5 SKIP. Zero falhas. Testes DQ-D-B: 3 PASS.

Escopo: dev-local, fixture sintetico. Nenhuma alteracao na Stable, indices reais, Qdrant instalado, fila real, ponteiro publico real, GUI operacional ou GitHub. A ativacao real da exclusao permanece bloqueada.