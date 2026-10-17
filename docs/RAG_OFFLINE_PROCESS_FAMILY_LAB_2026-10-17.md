# RAG   Auditoria de familias de processos (laboratorio)
Estado: SOMENTE LEITURA; NENHUM BACKUP REAL AUTORIZADO.

O inventario de identidades agora inclui ParentProcessId para cada
processo suspeito reconhecido. O modulo offline_process_family_audit
reconstroi a descendencia conhecida de um PID raiz, rejeitando entradas
duplicadas, identidades incompletas, parentesco circular e autorreferencia.

LIMITACAO CRITICA: offline_pid_identity_audit filtra apenas os processos
reconhecidos pelo diagnostico. Um filho que nao contenha os padroes
CodeBridge, mcp_server.py, adapter_server.py, Qdrant ou rag_index pode
nao constar. ParentProcessId e PID podem ser reutilizados entre leituras;
o resultado nao prova cadeia completa, ausencia de handles ou parada
da GUI/MCP. Uma segunda fonte de inventario integral e verificacao
de horario de criacao serao necessarias.

KNOWN_FAMILY_OBSERVED_UNPROVEN nunca libera captura:
copy_authorized=false, all_processes_known=false,
all_handles_closed=false, production_quiescence_proven=false.
Nenhum processo e interrompido, nenhum indice real e copiado.
