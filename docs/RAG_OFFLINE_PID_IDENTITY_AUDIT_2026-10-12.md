# RAG   Inventário externo de identidade de processos

Estado: diagnóstico somente leitura, NÃO autoriza cópia em produção.
Em Windows, usa Get-CimInstance Win32_Process, sem terminar serviços,
sem instalar pacotes e sem alterar configuração do CodeBridge.

Entrada independente:
`python rag_offline_pid_identity_cli.py`

O retorno é sempre código 2 para impedir interpretação como autorização.
Para processos suspeitos, apresenta PID, nome do processo, data de criação e
SHA-256 do caminho do executável. Nunca devolve CommandLine integral, pois
pode conter configurações ou segredos. Dados ausentes ou falhas de consulta
geram BLOCKED. Ausência de correspondência é apenas
NO_KNOWN_PROCESS_UNPROVEN, nunca evidência suficiente de quiescência.

O scanner identifica nomes CodeBridge/Qdrant e comandos associados ao
mcp_server.py, adapter_server.py e rag_index; processos Python que usam
outros entrypoints e handles herdados podem ficar fora do filtro.
A inspeção por PID não substitui rastreamento de handles ou encerramento
completo da GUI e de todos os indexadores. Nenhuma cópia é iniciada.
