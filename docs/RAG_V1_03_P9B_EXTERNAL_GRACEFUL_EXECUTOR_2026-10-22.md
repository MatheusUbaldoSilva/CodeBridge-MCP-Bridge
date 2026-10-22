# P9-B ? Executor controlado e recuperacao isolada

Data: 2026-10-22
Status: CODIGO PREPARADO E TESTADO COM FAKES; NAO EXECUTADO AO VIVO.

## Contratos novos

- installer/rag_p9b_shutdown_executor.py
  Verifica digest do plano atual, flag de canal independente, PID e
  create_time antes de enviar sinais. GUI recebe WM_CLOSE via HWND
  da janela CodeBridge 2.0 - MCP Bridge, validada por pid e titulo.
  Demais processos recebem terminate suave individualmente; nenhuma
  chamada kill e feita. Falhas nao sao tratadas como parada validada.
- installer/rag_p9b_external_recovery.py
  Verifica sete arquivos de arranque e relanca apenas a GUI via
  Pythonw, sem confirmar implicitamente o handshake do MCP.
- installer/rag_p9b_external_cutover_rehearsal.py
  Orquestracao com preflight digest, parada, prova de pos-parada
  e tentativa de recuperacao GUI, sem estagio de NSIS.
  A chamada isolada exige flags de execucao; nao existe CLI
  publicado para o operador executar inadvertidamente.
- tests/test_rag_p9b_shutdown_executor.py
- tests/test_rag_p9b_external_recovery.py
- tests/test_rag_p9b_external_cutover_rehearsal.py

## Evidencia

17 testes isolados com processos simulados PASS.
Nenhum processo real foi parado, nenhum instalador executado,
nenhum RAG, fila, worker ou scheduler alterado.
Esses testes NAO comprovam fechamento Win32 real nem reconexao MCP.

## Bloqueios antes do primeiro uso real

1. Confirmar canal externo independente estavel.
2. Melhorar a prova de reinicio e handshake real do MCP e tunel;
   GUI_PROCESS_RECOVERED nao e MCP_READY.
3. Testar recuperacao em processo isolado real sem tocar na GUI ativa.
4. Inspecionar condicoes de corrida e falha parcial no executor.
5. Validar novamente hashes NSIS, snapshot de 236 arquivos e
   processos via guard oficial sem contorna-lo.
6. Para instalar NSIS, promover artefato de preview pela rotina oficial
   e comprovar recuperacao; instalacao ainda NAO autorizada.

P9-B continua ABERTA.
