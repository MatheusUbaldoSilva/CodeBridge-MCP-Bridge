# RAG V1.03 — P9-B: contrato oficial de bootstrap MCP, sem ativacao publica

Data: 2026-10-22
Branch: rag-017-optimized-inference-after-candidate
Estado: IMPLEMENTADO NO CODIGO-FONTE; NAO CARREGADO/EXECUTADO NO MCP PUBLICO.

## Mudanca

Foi acrescentada a ferramenta de primeira parte
codebridge_rag_queue_bootstrap ao servidor author_mcp/mcp_server.py.

Modo padrao (execute=false):
- Inspeciona somente a raiz oficial LOCALAPPDATA/CodeBridge/rag.
- Exige ponteiro publico v1_delta_..., ausencia de journal de transicao,
  indice selecionado existente e fila ainda nao criada.
- Nao cria o diretorio jobs, arquivo SQLite ou fence.
- Retorna um plano, identificacao de geracao e uma string de confirmacao
  escopada ao digest do arquivo active-generation.json.

Modo de inicializacao (AINDA NAO EXECUTADO EM PRODUCAO):
- Requer execute=True, operator_approved=True, expected_generation exata e
  confirmation identica a que foi produzida pelo PREVIEW na mesma geracao.
- Apenas o booleano literal True permite entrar na operacao mutante.
- Bloqueia paths fora da raiz instalada, arquivos desconhecidos em jobs,
  transicao publica, journal pendente, ponteiro inesperado ou alterado.
- Cria somente jobs/incremental_jobs.sqlite3 versao 2 e
  jobs/supervisor_fence.sqlite3 versao 1, sob supervisor.lock exclusivo.
- Confere schema, fence e ponteiro antes de retornar sucesso.
- Nao inicia worker, scheduler, watcher, indexacao ou publicacao.
- Retornos de falhas depois de escrita sao marcados BOOTSTRAP_REVIEW_REQUIRED,
  com executado/arquivos parciais visiveis; NAO remove artefatos do operador
  automaticamente.
- Uma segunda tentativa depois do sucesso e bloqueada; jamais reinicializa
  nem sobrescreve fila preexistente.

## Evidencia de validacao

- O novo endpoint foi encontrado na lista de ferramentas de processo MCP
  Python novo; default execute=False confirmado no schema gerado.
- Testes com LOCALAPPDATA sintetico demonstraram preview sem side effects,
  confirmacao errada negada, inicializacao de fila e fence com autorizacao,
  protecao contra caminho externo e diretorio com arquivos desconhecidos,
  negativa em caso de journal, falha parcial de disco e mudanca do ponteiro.
- Testes MCP checaram erros estruturados, nao autorizacao implicita e ausencia
  de permissão de publicacao.
- NENHUMA chamada execute=True foi feita na instalacao real.
- Os testes NAO atestam que a ferramenta nova ja esta carregada no MCP
  atualmente conectado pelo ChatGPT.

## Procedimento de implantacao posterior

1. Confirmar Git HEAD=upstream e checkpoint atual; comprovar recuperacao
   da conexao MCP e tunel antes de reiniciar o servidor autoral.
2. Reiniciar/atualizar o MCP por seu fluxo oficial, sem quebrar CodeBridge.
3. Reestabelecer cliente MCP e conferir que aparece
   codebridge_rag_queue_bootstrap; testar primeiro apenas execute=False.
4. Examinar plano retornado, geracao, preflight, integridade publica e
   confirmacao de operacao explicitamente autorizada.
5. Executar SOMENTE a nova ferramenta oficial, nao contornar restricao antiga
   por PowerShell, Remote Desktop ou chamada direta do modulo.
6. Auditar fila, fence, filesystem, journal e busca publica; manter
   worker/scheduler desligados ate ensaio unico supervisionado.
7. Rollout incremental e rollback de geracao somente em fase separada.

## Limites

P9-B permanece EM ANDAMENTO. O RAG publico atual
v1_delta_1ae1d01ea84f4e (211 documentos, 8774 chunks) foi preservado.
O arquivo local nao versionado incremental_installed_queue_init.py
NAO foi utilizado nem modificado.
