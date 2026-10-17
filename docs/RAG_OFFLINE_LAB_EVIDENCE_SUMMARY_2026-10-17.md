# RAG - Laboratorio: consolidacao de evidencias de parada e restore

Estado: SOMENTE LABORATORIO; NAO AUTORIZA PRODUCAO.

offline_lab_evidence_summary.summarize_lab_evidence agrega relatorios
separados do supervisor de PIDs, probe de handles sinteticos e auditoria
de equivalencia da restauracao. Relatorios contraditorios, suspeitos ou
rejeitados deixam estado BLOCKED. Se todos os relatorios esperados estao
presentes, LAB_EVIDENCE_COLLECTED_NO_PRODUCTION_PROOF significa somente
que a cadeia sintetica apresentou as evidencias requisitadas.

Limite incondicional em todas as saidas:
copy_authorized=false
publication_authorized=false
production_quiescence_proven=false
all_handles_closed=false

Mesmo evidencias completas nao provam parada global de GUI, MCP,
indexadores ou mapeamentos de memoria. Inventario completo Win32 e
opcional como diagnostico; se informado e incompleto, bloqueia.
Nenhum processo real e encerrado e nenhuma copia real e efetuada.
