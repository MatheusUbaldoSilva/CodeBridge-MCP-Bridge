# RAG-DEL-01.04-P/Q/R — Barreira de workers (somente laboratório, DEV)

## Implementação confirmada

- knowledge_deletion_writer_fence_lab.py utiliza SOMENTE fila SQLite em TemporaryDirectory()/auto/jobs/auto_index_jobs.sqlite3. Rejeita caminhos de produção, redirecionamentos e arquivos inexistentes.
- Mantém BEGIN IMMEDIATE na fila e adquire guards injetados em ordem fixa: **queue -> generation -> semantic**. Não altera o catálogo, o ponteiro, os índices nem os leases.
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
