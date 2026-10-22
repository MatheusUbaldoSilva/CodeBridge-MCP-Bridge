# P9-B ? Supervisao externa e estado real do cutover

Data: 2026-10-22
Estado: AINDA BLOQUEADO. Nenhuma atualizacao real aplicada.

## Implementacao

- installer/rag_p9b_external_supervisor_preflight.py
- tests/test_rag_p9b_external_supervisor_preflight.py
- Codigo somente leitura, sem API para terminate/kill/install/restart.
- Identifica caminho exato da GUI, MCP, adapter e tunnel, PID e create_time.
- Distingue processos opacos, parent_pid ausente e idades inconsistentes.
- Codigo de saida 2 em situacao de bloqueio; NUNCA confundir sucesso
  da auditoria com permissao para aplicar instalador.
- Estado CLI real: SUPERVISOR_UPDATE_BLOCKED_RUNNING.

## Evidencia real de processos

GUI PID 1376, adapter PID 10768, tunnel PID 5608 e MCP PID 9300.
O PID pai historico do MCP e 10720, ausente no inventario atual.
mcp_parent_absent=[9300], parent_age_conflicts=[].
Um processo Windows com commandline opaca foi observado.
Bloqueadores: ADAPTER, GUI, MCP, TUNNEL.
A inspecao nao alterou nenhum processo.

## Qualidade

Suite integrada atual de P9-B, update guard e recovery:
102 testes PASS, em Python portatil do CodeBridge.
Os arquivos preexistentes continuaram intocados.

## Artefatos de reversao e instalacao

A pre-visualizacao vigente foi criada sobre c7b0a46:
CodeBridge-P9B-CURRENT-GUARDED-Preview.exe
SHA256=5e49d77d933744016276f460d3900aee1becadb0df430ba8aa459de5b03992fe

FULL_NSIS_PREINSTALL_SNAPSHOT.zip
SHA256=6f6cb339afd19e391233368858334a44fccbb86ad7a19422ec07ee79ae54e78b

Ambos em LOCALAPPDATA/CodeBridge-MCP-Bridge/release_staging/P9B_CURRENT_c7b0a46.
236 arquivos preservados e confirmados em ensaio isolado; 258 destinos.
Nunca misturar esse snapshot com executavel de outro hash.

## Pendencias de operacao

1. Definir/validar supervisor independente que nao dependa do MCP em parada.
2. Verificar identidade imutavel de GUI/MCP/adapter/tunnel e criar mecanismo
   oficial de encerramento com prova de parada e eventual ultimo recurso.
3. Antes de promover preview a instalacao, exigir nova auditoria de processo
   e rollback, e respeitar o guard oficial; nenhum executor pode contorna-lo.
4. Somente depois executar NSIS aprovado, relancar, validar reconexao real,
   ferramenta MCP bootstrap execute=false e indice publico.
5. Nao iniciar fila, worker ou scheduler antes de gate e aprovacao especificos.

P9-B continua aberta. Isto nao equivale a GO-LIVE aprovado.
