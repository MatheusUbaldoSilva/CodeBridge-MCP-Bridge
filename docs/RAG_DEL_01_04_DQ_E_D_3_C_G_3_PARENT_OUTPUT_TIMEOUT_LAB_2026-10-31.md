# RAG-DEL-01.04-DQ-E-D-3C-G-3 — Timeout do pai e filho sem resposta (DEV)

## Implementacao
- knowledge_deletion_liveness_parent_lab.py: _read_child_line_bounded limita a espera das linhas do worker a 7 s, tanto no preflight como na resposta apos ACK, com cap de 8192 caracteres. Trava da leitura gera RuntimeError e o finally do parent mata/recolhe o subprocesso antes de liberar generation(shared), semantic(exclusive) e catalog mutex. A leitura usa thread daemon apenas no laboratorio; a saida encerra a thread bloqueada ao fechar o pipe apos matar o filho.
- O parent de laboratorio suporta flags estritamente enumeradas --lab-hang-before-ready e --lab-hang-after-ready somente para os testes TEMP, sem chamadas externas a modelos/indices.
- knowledge_deletion_hang_worker_lab.py: fixture sintética que simula worker que trava antes ou depois de CHILD_VERIFIED, sem Qdrant/model/SQLite.

## Testes
3 testes novos: worker sem preflight atinge timeout e e recolhido liberando writer; worker sem resposta apos ACK atinge timeout e libera writer; CLI lab arbitraria e recusada. Pacote supervisionado 21 PASS.
Regressao RAG-DEL 438 (432 PASS, 6 SKIP), RAG-AUTO nonMCP 241 (236 PASS, 5 SKIP). Total 679 (668 PASS, 11 SKIP), zero falhas.

## Limites
O prazo e de laboratorio, nao time budget para modelos reais, e a thread de leitura nao e mecanismo autonomo de kill. O caller controla explicitamente Popen, kill/wait/close; nao promover sem projeto de timeout/cancelamento operacional, testes de handles e autenticacao de canal. O caminho instalado/Stable, a fila real, indices reais e GitHub nao foram alterados. Nao habilita exclusao.
Proximo: auditoria da seguranca da superficie MCP/GUI instalada e bloqueios do journal/READY_FOR_REVIEW, somente leitura inicialmente; operacional permanecera fechado ate aprovacao.