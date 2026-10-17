# RAG   Inventario completo de processos do Windows (laboratorio)
Estado: EXPERIMENTAL, SOMENTE LEITURA, NAO AUTORIZATIVO.

`rag.runtime.offline_full_process_inventory.inspect_full_process_inventory`
consulta Get-CimInstance Win32_Process sem coletar CommandLine e sem
expor caminhos de executaveis. Registra PID, ParentProcessId, nome,
horario de criacao e SHA-256 do caminho do executavel.
O PID 0 do kernel e contado e excluido da arvore de processos usuais.
Entradas sem caminho, horario ou parent valido elevam unverified_count
e mantem o estado BLOCKED. Uma falha de inventario, duplicacao
de PID ou parse invalido tambem bloqueia.

O modulo pode alimentar a auditoria de familias para localizar filhos
com nomes distintos, mas isso NAO prova inventario integral:
na estacao auditada, varios processos do Windows nao disponibilizam
ExecutablePath. Inventario parcial gera BLOCKED, sem falsa liberacao.

Limites de seguranca permanentes:
copy_authorized=false, all_handles_closed=false,
production_quiescence_proven=false. Nenhum processo e encerrado e
nenhum arquivo real do indice RAG e aberto por este diagnostico.
