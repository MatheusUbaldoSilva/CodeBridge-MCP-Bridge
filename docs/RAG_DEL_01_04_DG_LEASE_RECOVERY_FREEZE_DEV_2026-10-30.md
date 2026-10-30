# RAG-DEL-01.04-DG — Lease review e recuperação de órfão sob freeze (DEV)

## Inspeção somente leitura

knowledge_deletion_supervisor_review.inspect_deletion_supervisor_read_only agora aceita now_epoch opcional, com validação finita e não negativa. Classifica lease em NONE, ACTIVE, EXPIRED_RECONCILIATION_REQUIRED ou MALFORMED. Exibir o status não expõe token/ID de proprietário, não altera SQLite e NÃO prova ausência de processos legados.

Mesmo EXPIRED não libera exclusão nem recuperação automática. O bloqueador LEASE_RECONCILIATION_REQUIRED permanece até haver recuperação externa expressamente autorizada e verificada. Jobs não terminais continuam UNRESOLVED_QUEUE_JOBS.

## Ciclo real com fila sintética

Testes integram create_draft, aprovação, staging de Qdrant temporário, lease RUNNING e freeze FROZEN:

- Lease expirada pode ser recuperada com autorização pelo caminho existente recover_orphaned_auto_job, transformando RUNNING em QUEUED.
- O freeze NÃO desaparece na recuperação e impede a nova reserva central. A presença de QUEUED bloqueia quiescência, apesar de o lease ter sido liberado.
- Lease ainda não expirada recusa recuperação; sem operator_approved recusa recuperação e preserva o estado.
- Após thaw explícito e válido no laboratório, a reserva volta a ser possível.

Nos testes, semantic_guard_factory=nullcontext substitui o guard do worker, somente porque todas as fontes, catálogos, SQLite e vetores são sintéticos e isolados. Isso não certifica o procedimento de recuperação com worker real e LockFileEx semântico.

## Estado e próximo passo

RAG-DEL 286 testes (284 PASS, 2 SKIP) e RAG-AUTO exceto MCP 241 (236 PASS, 5 SKIP); 0 falhas. O caminho operacional permanece fechado, e a fila real não recebeu freeze, recovery ou cancelamento.

Pendências: prova do shutdown/drain dos processos físicos, pin de geração para toda sessão de leitura, integração com GUI/MCP, certificação de worker restart sob competição de lock Win32 e protocolo de replay idempotente.