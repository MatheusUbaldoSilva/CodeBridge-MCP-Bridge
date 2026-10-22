# P9-B ? Adaptador HKCU restrito

Criado installer/rag_p9b_winreg_adapter.py e sete testes
com winreg simulado. O adaptador possui whitelist fixa
de duas chaves HKCU pertencentes ao CodeBridge e dez valores
do instalador NSIS, com tipos REG_SZ/REG_DWORD.
A exclusao de uma chave previamente ausente e bloqueada
se encontrar subchaves ou valores de outro fornecedor,
sem ignorar dados inesperados.

Leitura REAL do registro Windows PASS:
Software\CodeBridge (InstallDir, Version);
Software\Microsoft\Windows\CurrentVersion\Uninstall\CodeBridge
(DisplayName, DisplayVersion, Publisher, InstallLocation,
DisplayIcon, UninstallString, NoModify, NoRepair).
Os valores reais nao foram exportados nesta auditoria.

IMPORTANTE: nenhum metodo de escrita foi chamado contra
o registro real. Falhas parciais e crash do processo ainda
exigem journal externo duravel e rollback por snapshot.
O adaptador nao autoriza NSIS nem restaura??o em producao.
