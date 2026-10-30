# RAG-DEL-01.04 — Gates operacionais ainda obrigatorios (auditoria DEV)

**Base de desenvolvimento:** commits P/Q/R, S, T, U/V e W do dia 2026-10-30.
**Resultado atual:** somente laboratorio de troca/recovery. Sem habilitacao de exclusao definitiva.

## Evidencias ja exercitadas

- Controle de journals e backups da geracao candidata antes da troca.
- Integridade e proveniencia verificadas sob mutex do catalogo (fase J-N).
- Fila SQLite sintetica com BEGIN IMMEDIATE e guards generation/semantic.
- LockFileEx real (canais generation e semantic), redirecionado exclusivamente a pastas temporarias.
- Rejeicao de leases, inclusive expiradas, e jobs nao terminais.
- Revisao do supervisor vinculada a geracao e identidade da fila; drift exige nova revisao.
- Queda forcada de processo antes e depois do swap temporario; rollback separado e validado.
- Resultado operacional sempre activation_authorized=False e operational_use_allowed=False.

## Bloqueios restantes antes de qualquer cutover real

1. **Drenagem e congelamento de novos trabalhos:** o supervisor atual reserva um job com BEGIN IMMEDIATE, mas o desenvolvimento ainda nao possui um estado de pausa operacional duravel e homologado para novas reservas durante a exclusao real. Uma barreira transitoria de laboratorio NAO atende a esse requisito.
2. **Participacao obrigatoria de todos os processos:** auditar readers, writers, GUI, MCP, workers semanticos e legados. Nao basta adquirir generation e semantic em um executor se qualquer caminho ignorar o contrato.
3. **Ordenacao global e prova contra deadlocks:** formalizar queue -> generation -> semantic ou outra ordem comum a todos, inclusive renovacao/release de leases e rotinas de recuperacao.
4. **Recuperacao de leases stale/expiradas:** a observacao atual e fail-closed. Nao remover lease automaticamente; implementar procedimento autenticado de reconciliacao de jobs e processos antes de declarar quiescencia.
5. **Prova de integridade dos dados reais:** snapshot consistente, validacao final de SQLite/FTS/Qdrant, arquivos preservados e hashes, tombstones, rollback apos falhas e verificacao de leitores reais, com execucao supervisionada.
6. **Revisao/confirmacao de exclusao:** vincular revisao do operador, geracao original, selecao, manifesto, hashes e estado da fila sob locks finais, sem aceitar evidencias antigas.
7. **Promocao e governanca:** auditar diff, testes e logs sem segredos, manter dados antigos recuperaveis, nao publicar ou mudar Stable sem aprovacao explicita.

## Inspecao somente leitura do supervisor, nesta sessao

Na consulta realizada, a fila local registrou um job READY_FOR_REVIEW e um CANCELLED, sem lease, geracao 41. Esse quadro e uma observacao momentanea e NAO prova estabilidade futura. Nenhum job foi cancelado ou alterado. O gate manteve UNRESOLVED_QUEUE_JOBS e nao autorizou exclusao.

## Criterio de continuidade

Comecar pela prova de congelamento duravel de novas reservas em ambiente isolado e sua observancia por todas as rotas de workers. Somente apos os demais gates e uma nova ordem expressa considerar uma transicao real. O desenvolvimento atual nao deve ligar o botao Excluir a escritor de catalogo operacional.