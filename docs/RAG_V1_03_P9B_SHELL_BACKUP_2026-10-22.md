# P9-B ? Backup complementar de registro e atalhos

Snapshot isolado do preview P9B_CURRENT_2d99ed4.
NSIS_SHELL_REGISTRY_SHORTCUT_SNAPSHOT.zip
SHA256 7d2e339b928e829b7be8d23e03def48e97127d78e093f183f159c58c633d2e511

Escopo controlado:
- HKCU Software\CodeBridge
- HKCU Software\Microsoft\Windows\CurrentVersion\Uninstall\CodeBridge
- 4 atalhos previstos no menu iniciar
- 1 atalho de desktop

Resultado SHELL_BACKUP_CREATED e SHELL_BACKUP_VERIFIED.
O snapshot e armazenado apenas na area release_staging local,
fora do Git, e nao exportado para o ChatGPT.
Nao foi criado mecanismo de restore real do registro ou atalhos;
a validacao confirma apenas consistencia do backup.

O atalho legado adicional de codificacao incorreta nao pertence
ao conjunto padrao NSIS e permanece intocado; uma restauracao
integral de todo ambiente deve considera-lo separadamente.
Quatro testes sinteticos aprovados.
P9-B ainda nao fechada; nenhum NSIS executado.
