# RAG-DEL-01.04-P/Q/R — Barreira de workers (somente laboratório, DEV)

## Implementação confirmada

- knowledge_deletion_writer_fence_lab.py utiliza SOMENTE fila SQLite em TemporaryDirectory()/auto/jobs/auto_index_jobs.sqlite3. Rejeita caminhos de produção, redirecionamentos e arquivos inexistentes.
- Mantém BEGIN IMMEDIATE na fila e adquire guards injetados em ordem fixa: **generation -> semantic -> queue (ordem corrigida em BB)**. Não altera o catálogo, o ponteiro, os índices nem os leases.
- Verifica schema esperado (PRAGMA user_version=1, tabelas do supervisor e singleton); recusa qualquer lease gravado, inclusive expirado, e quaisquer jobs fora de CANCELLED ou FAILED.
- Sempre libera locks e transação SQLite ao sair. Resposta contém operational_use_allowed=False e activation_authorized=False.
- Testes de processo independente comprovam que uma nova transação SQLite de reserva não obtém BEGIN IMMEDIATE durante a barreira temporária.
- Integração em diretórios de laboratório cobre troca/rollback preservando projeto vizinho, ponteiro público e prevenção quando há job ativo.
- Testes de encerramento abrupto por os._exit após journal PREPARED (com catálogo antigo e novo) demonstram reabertura da fila e recuperação separada via plan_lab_recovery/laboratory_rollback.

## Limites de homologação

**ESTE PATCH NÃO HABILITA EXCLUSÃO OPERACIONAL.**

1. Os guards são injetados, não o production_generation_lock. A prova de ordem de aquisição NÃO substitui auditoria de todos os readers e writers reais.
2. O supervisor real valida fontes antes de BEGIN IMMEDIATE; a barreira impede a RESERVA dentro da janela, mas não certifica trabalhos legados, leitores não cooperantes, dados persistentes ou novos jobs após sua liberação.
3. Não há ligação com UI de exclusão, alteração na Stable, promoção de geração privada, exclusão física ou push.
4. É obrigatória homologação posterior de ordenação global de locks, drenagem de workers, recuperação de leases e certificação de recuperação operacional com evidência de integridade.
5. Qualquer lease expirada falha fechada e exige reconciliação externa; não apaga nem modifica leases automaticamente.

## Validação

RAG-DEL: 222 testes, 220 aprovados, 2 dispensados, zero falhas no runtime Python DEV. Todos os novos testes utilizam dados artificiais sob Temp.
## RAG-DEL-01.04-S — Teste do lock Win32 real em fixture

Com unittest.mock.patch para redirecionar exclusivamente resolve_rag_sqlite_path a um CodeBridge/rag em TemporaryDirectory, os testes exercitam production_generation_lock (LockFileEx) nos dois canais reais. Outro processo recebe ProductionGenerationBusy enquanto ambos estao ativos, e apos liberar consegue adquirir. Se semantic estiver ocupado por processo concorrente, o lock generation e a barreira SQLite sao liberados. Nao ha abertura nem criacao de lock no root RAG do usuario.

## U/V — Orquestracao de laboratorio com revisao pinada

knowledge_deletion_fenced_swap_lab.py exige aprovacao explicita e catalogo temporario, valida revisao previamente observada do supervisor, pin da identidade do caminho da fila e da geracao do singleton sob a barreira SQLite, e chama laboratory_provenance_gated_swap somente com os dois guards adquiridos. Uma geracao diferente, lease ativo, revisao malformada ou caminho alterado bloqueia a transicao, sem autorizar uso operacional. A identidade de caminho em SHA-256 nao autentica a revisao e nao substitui comprovacao do estado dos workers reais.


## RAG-DEL-01.04-BB — Correcao de ordem por risco de deadlock

O contrato temporario foi corrigido de queue -> generation -> semantic para
**generation -> semantic -> queue**. Um worker existente pode possuir
semantic exclusivo e renovar o lease por SQLite em uma thread heartbeat.
Se o executor segurasse BEGIN IMMEDIATE na fila enquanto aguardasse semantic,
o heartbeat ficaria impedido de renovar e poderia causar espera circular,
timeout ou perda indevida do lease. A fila agora so e bloqueada APOS os guards
serem adquiridos, e o estado do supervisor/freeze e confirmado dentro do
BEGIN IMMEDIATE. O freeze duravel impede novas reservas na janela anterior.

O teste test_semantic_wait_does_not_block_worker_lease_heartbeat comprova
que um writer SQLite consegue abrir BEGIN IMMEDIATE enquanto a transicao
aguarda semantic. Outros testes confirmam que a fila fica bloqueada durante
o corpo da transicao e e liberada em erros ou rollback.

Esta alteracao NAO comprova que todos os caminhos de readers/writers
da instalacao obedecem generation -> semantic -> queue. A certificacao
global continua pendente; o adaptador permanece exclusivamente laboratorial.
