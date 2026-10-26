# RAG-AUTO-02 — Aceitação técnica do worker automático (DEV)

Data: 2026-10-26
Base anterior: a1ec581e732ea8b098e389e8695a243081d072d8
Branch: dev-local
Status: aceitação final / auditoria Git pendente de conclusão

## Escopo

RAG-AUTO-02.1 — contrato, limites e configuração CODE ubatch 32 / TEXT CPU
RAG-AUTO-02.2 — staging automático por job, SQLite, FTS5, manifesto e Qdrant
RAG-AUTO-02.3 — seleção determinística de lotes de até 256 vetores ausentes
RAG-AUTO-02.4 — checkpoints, validação, lease/fencing, reconciliação após falha
RAG-AUTO-02.5 — execução contínua limitada, supervisão de RAM e controle pela GUI/MCP
RAG-AUTO-02.6 — testes sintéticos, testes Jina reais isolados, auditoria de fechamento

## Fluxo implantado

Central RAG -> Adicionar -> selecionar fontes -> preparar e autorizar fila ->
Indexação automática -> Iniciar indexação -> confirmação explícita.
O worker é um processo Python separado, iniciado apenas pelo operador, com
argumentos validados. A consulta de status e o login não iniciam a GPU.
O executor percorre os lotes até READY_FOR_REVIEW, pausa, cancelamento,
falta de memória ou limite de lotes. A etapa de publicação pública não existe
no worker: pertence exclusivamente ao futuro RAG-AUTO-03.

Comandos MCP:
- codebridge_rag_auto_status
- codebridge_rag_auto_preview
- codebridge_rag_auto_approve
- codebridge_rag_auto_control
- codebridge_rag_auto_start (NOVO; execute/operator_approved/confirmation)

O início requer confirmation='RAG_AUTO_LAUNCH:<job_id>'. O subprocesso
exige confirmation='RAG_AUTO_RUN:<job_id>' e mantém PID e log separados.

## Segurança

- A autorização de arquivos é vinculada à lista aprovada + SHA256 e revalidada.
- Qdrant tem ids e payloads checados contra SQLite; diferenças interrompem.
- Apenas o portador atual do lease/fencing token pode atualizar o checkpoint.
- Pausa/cancelamento ao fim do lote. Fechamento da GUI solicita pausa
  para trabalhos QUEUED/RUNNING.
- O worker descarrega o modelo após cada lote, via _write_vectors.
- Limite inicial de RAM livre: 1600 MiB; CODE usa CUDA0 quando disponível
  (mantém fallback do modelo CODE); TEXT configurado exclusivamente em CPU.
- No máximo 256 embeddings por chamada, CODE ubatch32, 96 chamadas por
  execução automática por padrão (mais trabalhos exigem nova execução).
- Progresso é contabilizado pelo Qdrant efetivamente gravado.
- Falhas com escrita parcial geram estado PAUSED, salvam vetores persistidos
  e permitem retomada sem duplicação.
- Recuperação manual de orphan: exige operador, lease vencido/liberado,
  revalidação das fontes e lock semântico exclusivo.
- Subprocesso não herda variáveis arbitrárias do ambiente com credenciais.
- Nada grava no ponteiro público ativo, no SQLite/Qdrant da produção ou na stable.
- A fila de produção é criada somente na primeira aprovação real de fontes.

## Teste real Jina A — invocação CLI

Laboratório: C:\Users\Matheus\CodeBridge-RAG-Workspace\rag-auto02-canary-20261026
Job: af40480ef37e47b8a3f1b99caad36970
2 arquivos, 2 chunks, TEXT=1 (dimensão 1024), CODE=1 (1536).
2 lotes, 9s de execução observados.
Resultado: READY_FOR_REVIEW.
Qdrant/SQLite: validação PASS, published=false.
Modelos encerrados: llama-server=0.
Geração pública preservada: v1_delta_1ae1d01ea84f4e.

## Teste real Jina B — processo automático lançado

Laboratório: C:\Users\Matheus\CodeBridge-RAG-Workspace\rag-auto02-launch-canary-20261026
Job: 6c23672231d64960a260b81acc8ba8ad
Launcher retornou PROCESS_STARTED_UNVERIFIED, PID 6996.
O processo em separado concluiu com dois lotes, READY_FOR_REVIEW,
TEXT=1 e CODE=1; validação independente Qdrant/SQLite: PASS.
Log: ...\auto\logs\6c23672231d64960a260b81acc8ba8ad-20261026T144336223932Z.log
Subprocesso terminou; llama-server=0 após execução.
active-generation.json não foi modificado.

## Limitações transparentes

- Ainda NÃO testamos o *novo* worker com a carga total de 971 arquivos/11.385
  embeddings. A versão anterior dos scripts fez esse teste em laboratório;
  os dois testes atuais comprovam apenas o caminho ponta a ponta em escala pequena.
- A UI foi testada via QT offscreen e montagem MainWindow. Ainda falta a
  inspeção visual pelo operador após reabrir o DEV.
- A configuração CODE prefere a GPU CUDA0 com fallback; a telemetria disponível
  não prova separadamente qual backend executou cada inferência nesses dois ensaios.
- O progresso fica em READY_FOR_REVIEW. Qualquer cutover do RAG público exigirá
  autorização expressa, backup, rollback e implementação no RAG-AUTO-03.
- Cada job fica isolado no diretório do workspace; resultados não são
  automaticamente adicionados ao catálogo público.
- O limite de 96 lotes por execução evita loop infinito; trabalhos mais longos
  permanecem QUEUED para continuação explícita.
- O software solicita pausa na GUI ao fechar; o processo poderá terminar o
  lote atual antes do encerramento. Não é um kill forçado.

## Roteiro de regressão

DEV Python: executar testes `test_rag_auto_01_*.py` e testes `test_rag_auto_02_*.py`
exceto `test_rag_auto02_mcp_launch.py` (depende do Python MCP).
MCP Python: `test_rag_auto_mcp_tools.py` e
`test_rag_auto02_mcp_launch.py`.
Reexecutar regressões de indexação/pesquisa, teste de CPU fallback, Qt
e checagem `git diff --check`.
Não incluir arquivos preexistentes fora do escopo no commit.

## Percentual planejado

Após a auditoria final, RAG-AUTO-01 = 100%, RAG-AUTO-02 = 100%.
RAG-AUTO-COMPLETE = 40% (02 de 05 marcos, pesos iguais).
Essas métricas não representam publicação definitiva do RAG público.


## Fechamento dos testes e caminhos de staging

- RAG-AUTO-02 DEV: 32 executados, 31 PASS e 1 SKIP por aus?ncia de
  privil?gio Windows para criar symlink de teste; nenhum erro.
- RAG-AUTO-01 DEV: 53 executados, 52 PASS e 1 SKIP no Windows.
- Regress?es relacionadas: 35 PASS.
- MCP (ambiente autor_mcp dedicado): 8 PASS.
- Total das baterias do fechamento: **128 executados, 126 PASS, 2 SKIP, 0 FAIL**.
- AST: 25 m?dulos/fichas Python analisados sem erro.
- Seguran?a ampliada: stage_directory rejeita symlinks/junctions em
  caminhos do staging/SQLite/Qdrant/manifesto/progresso, e a fase recusa
  o stage j? existente caso possa redirecionar fora do workspace.
- Os testes MCP s?o separados da coleta DEV porque MCP usa venv
  pr?prio; n?o se deve interpretar falta de pacote MCP no DEV como
  falha da integra??o.
- Aprova??o manual antes de iniciar subprocesso; nenhum processo Jina
  inicia no import, no status, ou durante cria??o do job.
- Testes reais Jina A e B validam somente duas fontes por job, n?o
  a carga integral de 971 fontes deste projeto.
- Os testes do usu?rio na janela gr?fica real instalada continuam
  recomendados ap?s reinicializa??o normal do CodeBridge DEV.
