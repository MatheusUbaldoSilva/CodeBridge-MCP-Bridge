# P9-B ? Interrupcao de NSIS verdadeiro e recuperacao independente

Ambiente: Windows, NSIS makensis.exe instalado.
Laboratorio exclusivo: P9B_INTERRUPT_ba7ef39040924f26bc59c48b7ffcd4ef,
dentro de TEMP. Instalador minimo gerado fora do repositorio:
File first.txt; Sleep 15000; File second.txt.
Sem WriteReg, atalhos, servicos, atualizacao da instalacao ativa.

O primeiro script NSIS tinha erro de montagem das linhas por
PowerShell (compilacao recusada). Corrigida geracao pela
linguagem Python; compilacao NSIS verdadeira aprovada.
Durante o Sleep, o processo NSIS real foi terminado de forma
forcada; exit=-1. Aferido first.txt presente e second.txt
ausente: interrupcao ocorreu efetivamente no meio da instalacao.

Journal exclusivo salvo em release_staging:
P9B_INTERRUPT_ba7ef39040924f26bc59c48b7ffcd4ef_recovery.jsonl
Estados verificados:
SHELL_NSIS_INTERRUPTED
SHELL_NSIS_ISOLATED_RECOVERED
O recuperador em segundo processo Python confirmou exatamente
um arquivo no diretorio exclusivo, SHA256 do conteudo
023300e72502b681326eee673f12205fabeac02cad8f4e2d24c430f87e35d8ae,
removeu o arquivo e o diretorio e verificou sua ausencia.
Processo externo de recovery: exit=0.
RESULTADO: INDEPENDENT_REAL_NSIS_RECOVERY_VERIFIED.

Limite: este teste usou somente um arquivo sentinela, nao os
236 anteriores/22 novos do NSIS oficial, nem HKCU/atalhos
reais, nem restart publico do MCP. Nao equivale a pronto
para atualizar o CodeBridge instalado. P9-B ABERTA.
Proximos gates: expandir para NSIS com escopo completo
e rollback externo de arquivos, 2 HKCU, 5 atalhos;
prova de recuperacao e handshake publico, fechamento Git.
