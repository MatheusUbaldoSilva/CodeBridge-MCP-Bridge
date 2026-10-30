# RAG-DEL-01.04-Y/Z — Congelamento duravel de reservas (DEV/laboratorio)

## Escopo

O marcador auto_deletion_reservation_freeze no SQLite persiste FROZEN/OPEN, token de propriedade e generation monotona entre processos. A API de CRIACAO, congelamento e descongelamento e exclusivamente de laboratorio: aceita somente auto/jobs/auto_index_jobs.sqlite3 sob raiz temporaria de teste.

A funcao reserve_index_supervisor existente no DEV agora consulta o marcador OPCIONAL sob BEGIN IMMEDIATE antes de criar o lease. A mesma transacao SQLite evita a corrida entre uma nova reserva e o congelamento. Nao existe comportamento diferente em filas que nao possuem o marcador. Marcador presente e invalido causa recusa segura, nao limpeza automatica.

Freeze nao finaliza, pausa nem cancela workers ativos: a resposta registra workers_stopped=False. Renew e release de leases existentes nao sao impedidos, de modo a permitir drenagem supervisionada. Um freeze ativo bloqueia SOMENTE novas reservas pela rota central de reserve_index_supervisor.

A alteracao foi testada em processos diferentes, incluindo os._exit apos commit, concorrencia com BEGIN IMMEDIATE externo, reabertura de SQLite, recusa de thaw com token/generation antigos, e reversao explicita de freeze. Nenhum arquivo de RAG de producao foi escrito.

## Vinculacao ao gate isolado

Os modulos de review e writer fence observam o marcador sem criar tabela ou alterar estado. O adaptador laboratorio fenced provenance exige que o freeze seja FROZEN e que sua generation seja a revisada. Descongelamento e novo congelamento tornam a revisao anterior obsoleta.

A restricao de worker quiescence, levantada na etapa anterior, continua obrigatoria: mesmo com freeze valido, um job QUEUED/RUNNING/READY_FOR_REVIEW ou lease registrada impede troca. O token nao e exposto pela revisao somente leitura.

## Nao homologado

1. Nao confundir o gate do supervisor central com cobertura de workers legados, APIs externas ou caminhos que criam jobs sem reserve_index_supervisor.
2. Freeze e lock generation/semantic ainda nao formam um protocolo operacional unico certificado por todas as entradas.
3. Nao habilitar exclusao real, publicacao, alteracao de pointer, promocao privada ou mudanca na Stable.
4. O marcador de laboratorio nao e uma ferramenta administrativa para habilitar freeze na fila real.
5. A retirada de freeze operacional futura exigira procedimento explicito, verificacao de estado, auditoria e rollback.

## Testes

RAG-DEL 264 (262 PASS, 2 SKIP), RAG-AUTO sem caso MCP 241 (236 PASS, 5 SKIP). Total 505 executados, 498 PASS, 7 SKIP, 0 FAIL.
## Etapa AA — Revisao e revalidacao do freeze dentro do gate de transicao

A inspecao do supervisor em mode=ro observa reservation_freeze_active e reservation_freeze_generation sem revelar o token. O writer_fence recebe expected_freeze_generation e verifica FROZEN e a mesma generation sob a transacao BEGIN IMMEDIATE, antes dos locks generation/semantic. A revisao da candidata e recusada se o freeze for retirado ou recriado entre revisao e uso. Testes negativos incluem token nao exposto, marcador de schema incorreto e revisao desatualizada. O uso operacional continua desabilitado.
