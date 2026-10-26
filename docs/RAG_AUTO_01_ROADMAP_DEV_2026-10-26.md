# RAG-AUTO-01 — Controlador de indexação multiprojeto (DEV)

Data: 2026-10-26
Base DEV no início do trabalho: be9ef504a175eb3ec5ee14978152c6aa3570e184
Status: CONTROLADOR 01 PRONTO NO DEV — NÃO PUBLICAR, NÃO HABILITAR WORKER
Referência visual: painel preto, progresso verde, ações de pausar/retomar, perfil DEV, projeto e contadores.

## Premissas

- Usar os módulos atuais `rag/chunking`, `production_index`, `index_request`, `isolated_project_index` e validadores, sem refazer embeddings existentes.
- Separar rigidamente a fila de indexação multiprojeto do banco `%LOCALAPPDATA%/CodeBridge/rag/jobs/incremental_jobs.sqlite3` (este é exclusivo do `codebridge` e atualizações Git aprovadas).
- A nova fila será dedicada a indexação completa e atualização sob aprovação: `CodeBridge-RAG-Workspace/auto/jobs/auto_index_jobs.sqlite3`.
- Não modificar `%LOCALAPPDATA%/CodeBridge/rag/active-generation.json` ou as gerações públicas durante a construção e testes.
- Nenhum processo automático sem autorização do operador; importação de módulos não escreve banco, carrega Jina ou inicializa scheduler.
- Preservar tolerância à memória: GPU CODE ubatch32, CPU TEXT, um processo de modelo, RAM mínima de 1600 MiB antes de cada lote, checkpoint de vetor gravado no Qdrant.
- A geração DEV integrada em `be9ef50` permanece canário de leitura isolada e recuperável.
- As telas podem mostrar controles bloqueados até cada etapa estar validada; não transformar simulação em ação real sem implementação.

## Subfases e aceitação

**RAG-AUTO-01.1 — Auditoria e contrato**
Catalogar APIs já implementadas, escopo do novo componente, estados e invariantes. Resultado: este documento versionável; GitHub não atualizado.

**RAG-AUTO-01.2 — Fila SQLite isolada**
Persistência durável de rascunhos de indexação com project_id, caminho, escopo, chave idempotente, estados, contadores e eventos de auditoria. Reabrir sem perda, proteção contra duplicação, transação SQLite, testes de concorrência e migração segura. Nenhum worker.

**RAG-AUTO-01.3 — Inventário e aprovação explícita**
Usar preview de fontes, classificador de caminhos proibidos, contratos de revisão, versão Git (quando houver) e hash. Nenhuma fonte proibida entra na fila aprovada. Congelar o snapshot; revalidar antes de iniciar.

**RAG-AUTO-01.4 — Supervisor do job**
Leases exclusivos/geração para impedir dois Jina simultâneos, mecanismos de recuperação após crash e checkpoints com tokens de posse. O controlador não deve habilitar workers sem pré-requisitos.

**RAG-AUTO-01.5 — Pausa, retomada e cancelamento**
Solicitações persistidas, interrupção apenas em fronteira segura (batch/checkpoint), descarregamento de modelo, idempotência e bloqueio de resultados tardios.

**RAG-AUTO-01.6 — Telemetria e progresso**
Contagem real de documentos/chunks/vetores por tipo, porcentagem validada, RAM/VRAM, log limitado e eventos sem exposição de credenciais. Retomada lê Qdrant, não apenas um contador volátil.

**RAG-AUTO-01.7 — Interface QT**
Painel do mockup: cabeçalho Meus conhecimentos, projeto, arquivo/chunks, estado INDEXANDO/PAUSADO/VALIDANDO/PRONTO, barra verde, totais, perfil Jina (CODE GPU ubatch32, TEXT CPU), ações reais Pausar/Retomar/Cancelar, status de memória e detalhes de erro. Remover 'Simular conclusão'. Atualização por sinais Qt sem bloquear a GUI.

**RAG-AUTO-01.8 — MCP e DEV**
Status, listagem, autorização e comandos de controle conforme contrato; privilégios distintos para consultar e modificar. Testar DEV GUI e MCP públicos, preservando APIs antigas.

**RAG-AUTO-01.9 — Aceitação e fechamento**
Cenários: 971 arquivos com checkpoints, reiniciar aplicativo, queda de energia simulada, edição de fonte, limiar de memória, duplicidade, cancelamento gracioso, rollback do canário, busca semântica e FTS5. Auditoria diff/Git, commit e auditoria pós-commit somente ao final da fase funcional; nenhum push antes de autorização para publicação.

## Implementação inicial no DEV (não consolidada no Git)

- 01.1: contratos, escopo e critérios definidos após auditoria dos módulos existentes.
- 01.2: `rag/runtime/auto_index_queue.py` criado para rascunhos duráveis, sem aprovar nem iniciar indexação.
- Testes: `tests/test_rag_auto_01_queue.py`. SQLite transacional WAL + FULL, controle de concorrência, idempotência, eventos e leitura sem inicializar banco.
- O estado `DRAFT` **não é um job autorizado**; o campo `approved` permanece falso. Não há execução de modelos, monitoramento em background ou publicação.
- A API de persistência exige `allow_write=True`, e não está ligada aos botões da interface até o contrato de aprovação 01.3.
- Os dados de teste são gerados em pastas temporárias. Nenhuma nova fila foi inicializada no armazenamento de produção.
- Este é um checkpoint de desenvolvimento; o marco RAG-AUTO-01 **não foi fechado**, não houve commit e não houve push.

## Checkpoint de desenvolvimento — 2026-10-26

| Subfase | Estado atual | Prova |
|---|---|---|
| 01.1 | Contratos definidos | Auditoria do DEV e roadmap |
| 01.2 | Base SQLite validada | test_rag_auto_01_queue.py |
| 01.3 | Aprovação por SHA e fonte validada | test_rag_auto_01_approval.py |
| 01.4 | Reserva exclusiva/fencing validada; sem worker | test_rag_auto_01_supervisor.py |
| 01.5 | Controles persistentes validados; ACK futuro do worker pendente | test_rag_auto_01_controls.py |
| 01.6 | Telemetria verídica validada; contadores de worker pendentes | test_rag_auto_01_telemetry.py |
| 01.7 | Componente Qt pronto e testado isoladamente; falta montagem na janela principal | test_rag_auto_01_qt_card.py |
| 01.8 | Integração no MCP/GUI principal pendente de parada graciosa | Ainda não iniciado |
| 01.9 | Aceitação ponta a ponta e fechamento pendentes | Ainda não iniciado |

O componente visual está em `app_rewrite/rag_auto_job_card.py`, mas **não foi conectado à `RagPanel` carregada**: antes disso o usuário deve fazer parada graciosa da aplicação ativa. O mockup não foi convertido em um progresso falso; filas sem chunks mostram `--%`.

**Porcentagem de planejamento (não mede linhas, qualidade ou execução ponta a ponta):**
considerando nove subfases de peso igual, seis subfases de contrato testadas
(01.1–01.6) e metade da integração visual 01.7, temos
`(6+0.5)/9 ≈ 72%` de RAG-AUTO-01.
RAG-AUTO-COMPLETE considera inicialmente os cinco grandes marcos 01–05 com peso igual:
`72%/5 ≈ 14%`.
Essas porcentagens são estimativas conservadoras de planejamento, não prova de indexação automática operacional.

**Política de continuidade:** nenhum commit ou push intermediário, nenhum índice ativo
modificado, nenhum worker iniciado, nenhuma publicação de geração.
A integração operacional e a conclusão final exigem validação com o aplicativo
parado e reiniciado normalmente e a implementação do executor RAG-AUTO-02.

## Fechamento do controlador RAG-AUTO-01 (2026-10-26)

Após a parada graciosa, foi implementada a navegação da Central RAG, o
painel QT, o fluxo de autorização de fontes e as ferramentas de controle MCP.
O smoke de MainWindow e os testes de GUI/MCP passaram com serviços externos
simulados e bancos temporários. O arquivo de aceitação específico está em
`docs/RAG_AUTO_01_ACCEPTANCE_DEV_2026-10-26.md`.

As porcentagens de planejamento acima registram o ponto **anterior** à parada
graciosa. A avaliação após aceitar a fase passa a ser **RAG-AUTO-01 = 100%**
e **RAG-AUTO-COMPLETE = 20%**. O executor de embeddings RAG-AUTO-02
permanece pendente, portanto estes valores não significam indexação autônoma
de ponta a ponta.

## Limite entre RAG-AUTO-01 e demais marcos

01 entrega o controlador de trabalhos, estados, experiência de GUI e integração para disparar/observar o pipeline aprovado. O executor que cria embeddings com isolamento e recuperação completa será consolidado em RAG-AUTO-02; a promoção definitiva e incremental ficam em RAG-AUTO-03 e RAG-AUTO-05. Os botões só serão habilitados conforme capacidade real, sem simular sucesso.

## Fluxo pretendido

Selecionar projeto -> inventário e preview -> aprovar fontes/snapshot -> enfileirar -> supervisor garante exclusividade -> lotes Jina e checkpoints -> integridade e canário de leitura -> habilitar consulta; promoção do índice público exige aprovação independente e rollback.

## Política Git

- Exclusivamente `dev-local` no desenvolvimento; não editar stable.
- Não commitar por subfase e não enviar ao GitHub durante a construção.
- Concluir a fase com auditoria Git, revisão diff, testes, commit e auditoria pós-commit quando funcional; push somente ao final com autorização.
- Não tocar nos itens preexistentes fora do escopo (benchmark rag017 e dois arquivos não rastreados).
