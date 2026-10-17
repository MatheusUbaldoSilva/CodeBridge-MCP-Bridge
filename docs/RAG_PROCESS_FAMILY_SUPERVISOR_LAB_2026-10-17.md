# RAG   Supervisor de familia de processos, laboratorio (2026-10-17)

Estado: EXPERIMENTAL, nao e autorizacao para capturar dados reais.

O supervisor de saida de PIDs passou a rejeitar um PID que reaparece
apos a primeira ausencia observada. O novo offline_process_family_supervisor
avalia arvores conhecidas de processos em snapshots sinteticos e bloqueia
filhos que nascem durante o encerramento, filhos que aparecem apos a
saida do pai, retorno de um processo previamente ausente e mudanca
da identidade PID + creation time + fingerprint de executavel.

A consolidacao offline_lab_evidence_summary aceita o relatorio opcional
family_shutdown somente quando o estado e LAB_FAMILY_ABSENT_UNPROVEN,
sem erros e com copy_authorized explicitamente false. Resultados bloqueados
ou contraditorios nao podem compor evidencias satisfatorias.

ATENCAO: a familia conhecida e apenas a parcela identificada por
inventarios fornecidos. O nome do processo e o relacionamento PID/PPID
nao comprovam por si so todos os processos de GUI/MCP/adapter/indexadores,
handles SQLite/Qdrant e mapeamentos mmap. O retorno nunca habilita
backup ou publicacao real. Nenhum processo real e encerrado.
