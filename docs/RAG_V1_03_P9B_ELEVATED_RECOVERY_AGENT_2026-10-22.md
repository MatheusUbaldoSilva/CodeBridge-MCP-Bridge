# P9-B ? Supervisor elevado independente

Data: 2026-10-22
Estado inicial: CODADO, TESTADO EM ISOLAMENTO, SEM INSTALACAO NSIS.

Motivo: o CodeBridge GUI executa com nivel de integridade Alto
(administrador, S-1-16-12288), enquanto o Remote Desktop Commander
executa com integridade Media (S-1-16-8192). O Windows negou
PostMessage(WM_CLOSE) do remoto inferior, erro 5 ACCESS_DENIED.
O processo elevado do CodeBridge enviou com sucesso WM_NULL
na mesma GUI em modo nao mutante, Win32 error 0.

Criado installer/rag_p9b_elevated_recovery_agent.py.
Roteiro: agente separado sob integridade elevada, digest exato
do plano, journal atomico em disco, parada graciosa, prova
externa de pos-parada, tentativa automatica de recuperar GUI,
sondagem local adapter/MCP. A rotina NAO instala NSIS, nao
inicializa filas e jamais alega handshake publico ChatGPT.

Os testes sinteticos impedem mutacao sem duas flags e elevacao,
falham para digests divergentes, cobrem parada parcial/excecao e
recuperacao local. 8 testes PASS.
Processo elevado separado PID5788 executou --dry-run corretamente,
escreveu AGENT_DRY_RUN_ONLY. O Remote Desktop independente leu
exatamente o mesmo journal no disco sem interrupcao do CodeBridge.

Importante: GUI recuperada e MCP local online nao significam
conexao publica restaurada. Validar o estado pela API ChatGPT
apos a conclusao do ensaio sem NSIS.
