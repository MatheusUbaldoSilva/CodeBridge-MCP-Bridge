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
