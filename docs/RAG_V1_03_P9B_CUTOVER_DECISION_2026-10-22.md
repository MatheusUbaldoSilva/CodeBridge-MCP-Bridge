# P9-B ? Decisao de cutover read-only

Data: 2026-10-22
Status: INSTALACAO CONTINUA BLOQUEADA.

Novo gate installer/rag_p9b_cutover_decision.py valida em conjunto:
hash exato do instalador, hash do ZIP rollback, manifesto que os
associa, baseline 236 arquivos, geracao RAG publica, comprovante
de recuperacao externa, restauracao scratch e guard de processos
NSIS em tempo real.

A prova sobre a instalacao atual retornou:
P9B_CUTOVER_REFUSED
reason=NSIS_PROCESS_GUARD_BLOCKED
blockers=CODEBRIDGE_GUI_RUNNING, CODEBRIDGE_MCP_RUNNING
installed_modified=false
installer_executed=false
operator_execution_authorized=false

O modulo nao realiza parada, update, instalacao ou rollback.
Mesmo com todos os gates observados, retorna apenas
P9B_PREFLIGHT_OBSERVED_ONLY, sem autorizar execucao.
Validado por seis testes de falha/permissao.
O processo NSIS deve repetir seu proprio guard antes de
sobrescrever arquivos e a recuperacao externa precisa
continuar disponivel durante o update real.

Hash do instalador: 0898124096989d62fd438395bc6f01baa031516f2579860daf275471272e3223
Hash ZIP rollback: ad8d8c6397a1421a5858fb2f1b1746cfbda941d378cedd7b268b3931bb5fdf0d
Fonte de build exata: 2d99ed46435b44d25d5200cfa74a18f1ec24c4a8
Os tres arquivos locais pendentes nao entraram no instalador.
