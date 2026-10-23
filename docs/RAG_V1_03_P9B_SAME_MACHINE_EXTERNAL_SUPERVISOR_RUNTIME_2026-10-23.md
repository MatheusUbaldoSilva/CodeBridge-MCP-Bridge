# P9-B ? Python externo ao CodeBridge na mesma maquina Windows

Preparado ambiente privado em LOCALAPPDATA/CodeBridge-MCP-Bridge/
release_staging/P9B_HEAD_CANDIDATE_f45880511c/external_supervisor_lib.
O psutil foi copiado para staging SEM modificar a versao
instalada do CodeBridge. Python executado:
LOCALAPPDATA/Programs/Python/Python313/python.exe
Verificado que sys.executable e psutil.__file__ NAO apontam
para a instalacao do CodeBridge, reduzindo a dependencia
durante desligamento do proprio MCP.

Novo ponto de entrada de inspe??o estritamente read-only:
installer/rag_p9b_same_machine_external_probe.py.
Exige Python e psutil externos, manifesto dentro do staging,
SHA256 da identidade de transacao, snapshot de arquivos,
HKCU, atalhos, preimagem e topologia de processos.
Resultado observado no Windows atual:
EXTERNAL_READ_ONLY_PREFLIGHT;
CURRENT_MACHINE_CUTOVER_REFUSED;
PROCESSES_NOT_EXTERNALLY_STOPPED;
production_modified=false.
Nao emite sinais, nao executa NSIS, nao altera registro.

Pendencia impeditiva: executor de rollback de PRODUCAO que
restaure arquivos/registro/atalhos sob supervisor externo
com verificacao independente de processo parado. As provas
anteriores de rollback foram em pasta temporaria.
A atualizacao oficial segue bloqueada ate esse ponto.
