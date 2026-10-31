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
3. **Ordenacao global e prova contra deadlocks:** formalizar generation -> semantic -> queue (ordem revisada em BB) ou uma ordem global homologada, inclusive renovacao/release de leases e rotinas de recuperacao.
4. **Recuperacao de leases stale/expiradas:** a observacao atual e fail-closed. Nao remover lease automaticamente; implementar procedimento autenticado de reconciliacao de jobs e processos antes de declarar quiescencia.
5. **Prova de integridade dos dados reais:** snapshot consistente, validacao final de SQLite/FTS/Qdrant, arquivos preservados e hashes, tombstones, rollback apos falhas e verificacao de leitores reais, com execucao supervisionada.
6. **Revisao/confirmacao de exclusao:** vincular revisao do operador, geracao original, selecao, manifesto, hashes e estado da fila sob locks finais, sem aceitar evidencias antigas.
7. **Promocao e governanca:** auditar diff, testes e logs sem segredos, manter dados antigos recuperaveis, nao publicar ou mudar Stable sem aprovacao explicita.

## Inspecao somente leitura do supervisor, nesta sessao

Na consulta realizada, a fila local registrou um job READY_FOR_REVIEW e um CANCELLED, sem lease, geracao 41. Esse quadro e uma observacao momentanea e NAO prova estabilidade futura. Nenhum job foi cancelado ou alterado. O gate manteve UNRESOLVED_QUEUE_JOBS e nao autorizou exclusao.

## Criterio de continuidade

Comecar pela prova de congelamento duravel de novas reservas em ambiente isolado e sua observancia por todas as rotas de workers. Somente apos os demais gates e uma nova ordem expressa considerar uma transicao real. O desenvolvimento atual nao deve ligar o botao Excluir a escritor de catalogo operacional.
## Atualizacao apos a fase DO — 2026-10-30 (somente DEV)

**Codigo de referencia antes da consolidacao DP:** 802deed, branch dev-local. Nenhuma operacao de conhecimento real foi autorizada.

### Avancos confirmados

- Y/Z: marcador duravel de freeze somente em banco TEMP, com verificacao atomica no ponto central de novas reservas.
- BB: a ordem correta do executor LAB passou a ser generation -> semantic -> queue, com teste de heartbeat SQLite quando outro processo detem semantic.
- DE/DF/DI: leitura de ponteiro de worker, agendador e leitor versionado reforcadas com lock compartilhado, journal pendente e verificacao contra redirecionamento.
- DJ/DL: listagem publica codebridge na GUI ja usa o helper de inventario pinado durante toda a consulta SQLite. O commit DL foi seletivo: 8 linhas novas, preservando 30 adicoes e 3 remocoes preexistentes do usuario na interface.
- DG/DH: recuperacao de lease expirada e crash de processo em fixtures; lease persistida e jobs nao terminais continuam bloqueando ativacao.
- DM: demonstracao scratch-only de leitura privada serializada pelo mutex do catalogo; NAO conectada a leitores reais.
- DN: tres testes Qt comprovam estado da GUI durante busy/falhas, sem habilitar exclusao.
- DO: registro de codebridge_rag_generation_probe encontrado no servidor MCP e testes de fonte/AST, mas a ferramenta nao aparece nesta conexao; processo MCP instalado NAO atestado.

### Bloqueios operacionais que permanecem

1. Freeze duravel operacional e drenagem de workers ainda nao foram homologados; freeze de laboratorio nao pode ser aplicado a fila real.
2. Leitores privados GUI/MCP/search/get-context continuam sem contrato universal de pin de catalogo durante toda a consulta.
3. A disponibilidade real do probe MCP e seu resultado no processo em execucao nao foram confirmados; semantic child worker tampouco foi atestado.
4. A fila real pode manter READY_FOR_REVIEW, DRAFT/QUEUED ou leases que exigem reconciliacao; nunca limpar automaticamente como efeito colateral de delecao.
5. Falta certificar read-path real Qdrant/SQLite, snapshots, cancelamento seguro, rollback e processo de aprovacao explicita.
6. A instalacao Stable, publicacao no GitHub, exclusao definitiva e a ponte de ativacao privada continuam proibidas neste escopo.

### Evidencia de regressao atual

RAG-DEL 315 testes (312 PASS / 3 SKIP); RAG-AUTO non-MCP 241 testes (236 PASS / 5 SKIP); total 556 testes, 548 aprovados, 8 dispensados, zero falhas. O teste MCP que depende do pacote Python mcp segue excluido.

**Proxima etapa recomendada:** DQ — certificar o ciclo de vida de uma sessao privada com catalogue pin e semantic lock entre processos, em TEMP, com timeout/fail closed. Depois homologar os leitores reais antes de conectar qualquer exclusao operacional.