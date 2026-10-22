# P9-B ? Prova de saude local depois do restart

Data: 2026-10-22
Status: LOCAL_ADAPTER_AND_MCP_READY, resultado observado SEM restart real.

## Acrescimos

- installer/rag_p9b_poststart_health.py
  Carrega o probe local instalado, confirma adapter e MCP ONLINE.
  Nunca traduz esse resultado em public_mcp_handshake_verified=True.
- tests/test_rag_p9b_poststart_health.py
  Quatro testes, inclusive adapter em DEGRADED e falha de leitura.
- installer/rag_p9b_external_cutover_rehearsal.py
  Cobertura adicional para excecao no posstop e na recuperacao,
  preservando tentativa de recuperar GUI apos parada completa.
- tests/test_rag_p9b_external_cutover_rehearsal.py
  Testes de falha parcial e recuperacao sem alegar MCP publico pronto.

## Verificacao real

O probe contra a instalacao ATIVA retornou:
LOCAL_ADAPTER_AND_MCP_READY
verified=true
public_mcp_handshake_verified=false
installer_executed=false

Nao foi realizado encerramento, novo startup, instalacao NSIS,
ativacao da fila ou publicacao do RAG.

## Restricoes

O comando de cutover real ainda NAO foi habilitado.
Os executores foram validados somente com mocks/processos simulados.
A transicao de GUI real requer canal externo, recuperacao garantida
e novo handshake MCP visto pelo cliente apos o retorno.
P9-B permanece ABERTA.

## Regressao integrada e verificacao externa

Apos as correcoes de recuperacao e saude local, o conjunto integrado
P9-B + lifecycle + guard NSIS passou 152 testes.
O preflight independente no Remote Desktop ainda observa GUI1376,
MCP9300, adapter10768 e tunnel5608; 54 processos opacos gerais mas
zero candidatos CodeBridge opacos. Nao foi efetuada parada real.

## Gate integrado adicional

O orquestrador agora exige verificar LOCAL_ADAPTER_AND_MCP_READY
apos recuperar GUI e antes de retornar estado de stack local.
Mesmo o estado CUTOVER_LOCAL_STACK_RECOVERED mantem
mcp_handshake_verified=false, e exige reconexao publica real.
Nao ha ainda prova de reinicio real do processo MCP.

## Regressao e sessao Windows

153 testes integrados PASS apos o novo gate de MCP local.
O Remote Desktop e a GUI do CodeBridge pertencem ambos
a SessionId 1 do Windows, assim como MCP, adapter e tunnel.
A prova de SessionId e somente read-only; nao garante por si
que o processo pythonw apos restart fara handshake com ChatGPT.
A recuperacao GUI exige ainda validacao operacional externa.
