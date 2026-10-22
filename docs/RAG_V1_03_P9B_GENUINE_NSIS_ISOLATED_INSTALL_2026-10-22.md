# P9-B ? NSIS verdadeiro em instalacao isolada

Auditoria: a base installer/RAG017_Isolated_Test.nsi utiliza
InstallDir em TEMP, RequestExecutionLevel user, SilentInstall
silent e apenas File/SetOutPath. Nao escreve no registro,
nao cria atalhos, nao instala os servicos do CodeBridge.

O script foi copiado temporariamente com destino exclusivo
P9B_NSIS_E2E_776eb298337a4255ae2fc87493d84c6b
sob TEMP, e executavel de teste guardado no release_staging.
Compilador local NSIS makensis.exe: exit=0.
Executavel NSIS real chamado com /S: exit=0.
Resultado observado: 179 arquivos no diretorio TEMP exclusivo.
Script .nsi temporario eliminado apos teste.

Este marco comprova instalacao isolada de payload real,
nao rollback por interrupcao, nem HKCU real, nem upgrade do
produto instalado. P9-B ABERTA. Proximo passo: teste de
falha controlada DURANTE NSIS, mantendo toda mutacao em
laboratorio descartavel, seguido de recuperador independente,
conferencia de arquivos/registro e integridade do MCP.
