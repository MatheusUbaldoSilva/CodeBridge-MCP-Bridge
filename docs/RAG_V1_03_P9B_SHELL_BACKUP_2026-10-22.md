# P9-B ? Backup complementar de registro e atalhos

Snapshot isolado do preview P9B_CURRENT_2d99ed4.
NSIS_SHELL_REGISTRY_SHORTCUT_SNAPSHOT.zip
SHA256 7d2e39b928e829b7be8d23e03def48e97127d78e093f183f159c58c633d2e511

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


## Restaura??o isolada do escopo complementar

Implementado installer/rag_p9b_shell_restore_scratch.py e testes.
Reproduziu os cinco arquivos de atalho para SHELL_SCRATCH_RESTORE
e exportou as duas chaves para um JSON de revis?o em pasta isolada.
Resultado independente via Remote Desktop:
SHELL_SCRATCH_RESTORE_REHEARSED
shortcut_files=5; registry_keys_reviewed=2;
real_shortcuts_modified=false; registry_modified=false.

Essa prova NAO restaura o HKCU nem os atalhos em produ??o.
O rollback do NSIS continua pendente de executor auditado
e verifica??o p?s-restaura??o real quando apropriada.


## Plano de restauro fail-closed

installer/rag_p9b_shell_restore_plan.py prepara plano por identidade
de cada um dos 5 links e 2 chaves HKCU. Recusa processos ainda ativos,
SHA incorreto, alvos simbolicos, nomes/slots alterados, members extras
no ZIP e conteudos com digest diferente. 5 testes sinteticos PASS.

O teste na instalacao ativa recusou como
INSTALLATION_MUST_BE_STOPPED. O ensaio somente de planejamento
com indicador sintetico de processos parados retornou
SHELL_RESTORE_PLAN_ONLY. Nunca modificou registro ou atalhos.

O hash anterior do snapshot de shell tinha transcricao com um
caractere a mais. SHA256 correto obtido por Get-FileHash diretamente
do ZIP: 7d2e39b928e829b7be8d23e03def48e97127d78e093f183f159c58c633d2e511.
