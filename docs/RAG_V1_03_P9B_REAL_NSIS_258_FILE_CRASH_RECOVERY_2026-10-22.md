# P9-B ? Interrupcao real de NSIS com 258 destinos e rollback

Teste Windows em laboratorio descartavel, sem modificacao
na instalacao ativa ou registro/atalhos reais. Utilizado ZIP
aprovado FULL_NSIS_PREINSTALL_SNAPSHOT.zip: 258 destinos,
236 existentes e 22 novos. Preparados arquivos antigos
com bytes reais do backup no diretorio TEMP exclusivo.

Gerado instalador NSIS real em release_staging para gravar
sentinela de laboratorio nos 22 destinos novos e no primeiro
arquivo antigo, Sleep 15000, depois nos restantes.
Primeira compilacao falhou na sintaxe NSIS /oname com
aspas; corrigida. Segunda compilacao: exit=0.

NSIS /S executado e interrompido apos escrita das 22
sentinelas novas e primeiro antigo, antes dos restantes.
Processo terminou com codigo 1. Criado journal persistente
com fsync SHELL_NSIS_FULL_SCOPE_INTERRUPTED.
Outro processo Python executou o restaurador ja versionado
installer/rag_p9b_file_restore_executor_lab.py
contra o snapshot aprovado. Recuperador: exit=0.
Resultado FILE_RESTORE_LAB_VERIFIED, old_files=236,
new_files_removed=22, verified=true,
production_modified=false.
Segundo evento do journal: SHELL_NSIS_FULL_SCOPE_RECOVERED.

Limite: NSIS de LABORATORIO gerado para respeitar os
258 destinos do snapshot, nao e o instalador completo oficial.
Ainda faltam rollback efetivo HKCU real/atalhos, supervisor
externo elevado, validacao de poststart e handshake publico
do MCP. P9-B ABERTA e main intacta.
