# RAG V1.03 — P9-B: bootstrap instalado e politica MCP (adicao)

Data: 2026-10-22
Branch: rag-017-optimized-inference-after-candidate
Estado: P9-B EM ANDAMENTO. Bootstrap e scheduler de producao NAO executados.

## Problema instalado comprovado

- Raiz: C:\Users\Matheus\AppData\Local\CodeBridge\rag
- Geracao publica: v1_delta_1ae1d01ea84f4e, READY.
- 211 documentos e 8774 chunks.
- Ponteiro active-generation.json presente e valido.
- Journal production-generation-transition.json ausente.
- O DIRETORIO rag\jobs esta ausente, logo jobs\incremental_jobs.sqlite3
  e jobs\supervisor_fence.sqlite3 tambem estao ausentes.
- Essa situacao difere de um SQLite corrompido ou schema desatualizado.

## Entregas tecnicas nesta subetapa

- rag/runtime/incremental_installed_queue_bootstrap_preflight.py:
  analise somente leitura que separa diretorio ausente, schema ausente,
  fila versionada, schema antigo, arquivo estranho, ponteiro publico
  alterado e journal pendente.
- rag/runtime/incremental_installed_scheduler_preflight_cli.py:
  --show-bootstrap inclui essa analise no diagnostico existente.
- Este preflight NUNCA cria diretorio, fila, fence ou servico.
  Resultado BOOTSTRAP_BLOCKED, com permission_to_bootstrap=false.
- rag/runtime/incremental_offline_worker.py:
  heartbeat so aceita segundos numericos finitos em [0.01,30].
  NaN, infinito, bool, texto e intervalos fora de faixa nao podem chegar
  a reserva de job.
- tests/test_incremental_p9b_public_index_guard.py:
  prova que o endpoint MCP codebridge_rag_index execute=true continua
  NEGADO quando a configuracao de RAG V1 e ativa, mesmo se existir
  adaptador de staging registrado.
- tests/test_rag_017_installed_bridge_safety.py:
  teste de desativacao padrao isolado da opt-in real do operador; a busca
  semantica instalada NAO foi desligada.

## Por que nao reabilitar simplesmente o executor de indexacao MCP?

Em author_mcp/rag_bridge.py, index_rag() contem um bloqueio EXPLICITO
para execute=true quando rag_v1_semantic.json aprova o CodeBridge.
A indexacao publica da V1 exige fluxo independente de aprovacao de fontes,
lock de geracoes e autorizacao de manutencao.
Remover esse bloqueio para criar a fila seria uma falsa solucao e poderia
produzir publicacao sem gate. Nao foi removido.

## Testes e comandos de diagnostico

Executar SOMENTE leitura:
  python -m rag.runtime.incremental_installed_scheduler_preflight_cli --show-bootstrap

Se for necessario exit-code de readiness:
  python -m rag.runtime.incremental_installed_scheduler_preflight_cli --require-ready --show-bootstrap

Este segundo comando retorna 2 quando prerequisitos nao estao presentes.
A fila e a publicacao continuam inativas independentemente de qualquer
relatorio chamado OBSERVED_ONLY.

Testes: bootstrap temporario v2, ausente, esquema antigo, banco estranho,
journal e pointer switch; heartbeat; bloqueio MCP e isolamento do teste.

## Proximo passo seguro

1. Definir um fluxo de bootstrap explicito e auditavel no proprio MCP
   (com aprovacoes e schema versionado), em vez de executar comandos
   alternativos para contornar o bloqueio conhecido.
2. Validar criacao de jobs + fence + lock no armazenamento instalado pelo
   metodo autorizado e comprovar que nao altera a geracao publica.
3. Habilitar apenas uma execucao de job com Git/SHA/lease aprovados,
   executando staging offline; provar retry, crash e retomada.
4. Em etapa SEPARADA, validar o gate de publicacao e rollback de geracao.
5. Somente apos isso marcar P9-B e automacao V1 como concluidas.

## Integridade de historico

Os arquivos anteriores benchmark modificado, rollback runbook e o
rascunho local incremental_installed_queue_init.py foram preservados.
Nenhuma fila instalada criada e nenhuma geracao publica substituida.
