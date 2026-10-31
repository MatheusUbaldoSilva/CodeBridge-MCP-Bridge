# RAG-DEL-01.04-DQ — Plano de pin de leitura privada e prevençao de deadlock

Data: 2026-10-30. Estado inicial: PLANEJADO, aguardando desenvolvimento isolado. Referencia: dev-local 621bd80. Nenhuma mudança operacional autorizada.

## Problema tecnico

- A troca privada em laboratorio usa generation -> semantic -> queue -> catalog mutex.
- A busca privada search_isolated_project resolve o registro e consulta o SQLite; para inferencia semantica chama semantic_isolated_project, que adquire o lock semantic dentro de sua propria funcao.
- Envolver a busca no mutex de catalogo sem mover o lock semantic poderia inverter a ordem catalog -> semantic, enquanto o swap usa semantic -> catalog, criando ciclo potencial.
- Se o leitor externo ja detiver semantic e o executor semantico interno tentar readquirir o mesmo lock, a interface tambem pode travar.
- O catalog mutex usa msvcrt.LK_LOCK bloqueante, ainda sem politica de timeout para GUI/MCP.
- O laboratorio DM comprovou apenas inventario SQLite sob mutex; NAO comprovou busca semantica, get-context ou reader/writer global.

## DQ-A — Congelar contrato e levantar entradas

Mapear todas as entradas privadas de search, get-context, listagem GUI, MCP, subprocessos e recovery. Formalizar um contrato unico para leitores com ordem generation(shared) -> semantic(exclusive, quando necessario) -> queue (se exigido) -> catalog. Distinguir leitores puramente lexicais de leitores com semantica. Produzir teste de contrato antes de alteracoes no codigo operacional.

## DQ-B — Guard cooperativo em root TEMP

Criar guard de laboratorio com TryLock/timeout limitado e caminhos isolados, sem bloquear indefinidamente o worker Qt. Nao criar nem alterar arquivos reais de lock. Exigir evidencias de identidade de catalogo, revisao, hash SQLite/manifesto e nenhum journal pendente. Falar em pin somente quando a trava for mantida durante toda a leitura.

## DQ-C — Busca/contexto com lock semantico nao reentrante

Testar busca SQLite e contexto mais inferencia semantica sintetica sob a mesma geracao. Evitar adquirir semantic duas vezes: separar executor que toma o lock e executor que exige lock ja detido (contrato explicito). Durante a leitura, swaps concorrentes devem aguardar ou recusar sem alterar a geracao de retorno.

## DQ-D — Falhas concorrentes e recuperacao

Subprocessos reais Windows: lock generation shared versus exclusive, semantic ocupado, fila com heartbeat, catalog mutex por dois processos, timeout, kill/os._exit, reabertura e rollback. Invalidar evidencias antigas e recusar catálogos com journal pendente.

## DQ-E — Gates de producao e integracao

So apos DQ-A..D aprovados, auditar chamadas MCP realmente carregadas e GUI instalada, idealmente expondo o probe MCP ja registrado no servidor. A fase NAO liga botão de excluir, não promove indice, não escreve na fila real e não faz push. Qualquer piloto operacional exige ordem explícita e rollback comprovado.

## Criterios de fechamento

Cada letra exige testes isolados, auditoria de diff, patch notes, commit seletivo e auditoria pós-commit. Uma fase pode estar fechada no laboratorio sem autorizar o uso operacional. Os cinco arquivos de trabalho preexistentes seguem preservados.