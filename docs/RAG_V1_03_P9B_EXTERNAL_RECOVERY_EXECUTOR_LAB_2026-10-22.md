# P9-B ? Recuperador externo em laborat?rio

Modulo: installer/rag_p9b_external_recovery_executor_lab.py.
Executa restauracao apenas em laboratorio descartavel,
sem NSIS, HKCU ou processos da instalacao em producao.

Requer identidade persistente validada dos quatro artefatos,
marcador explicito de laboratorio e hash exato do ZIP de
arquivos. Exige resultado de recuperacao e pos-verificacao.

Ensaio Windows P9B_EXTERNAL_RECOVERY_E2E_V2_20261022:
UNIFIED_LAB_READY; processo de simulacao interrompido
por os._exit(83); EXTERNAL_LAB_RECOVERY_VERIFIED.
Conferidos 236 arquivos anteriores, remocao de 22 destinos
novos, 5 atalhos e 2 chaves de registro SIMULADAS.
nsis_executed=false; production_modified=false.

Cinco testes do modulo PASS, incluindo recusa por identidade
do laboratorio, ZIP divergente, e rollback nao verificado.
Falta comprovar supervisor com NSIS real, rollback Windows
com HKCU, restauro da stack e handshake publico do MCP.
P9-B continua ABERTA.
