# P9-B ? Topologia real MCP filho de GUI validada

A inspecao externa independente no Windows atual encontrou
GUI, MCP, ADAPTER e TUNNEL unicos e identificados.
O MCP e filho direto da GUI (parent_pid igual ao PID GUI),
com create_time posterior; nenhum conflito de idade detectado.
A regra anterior so aceitava MCP orfao e recusava
UNEXPECTED_MCP_ANCESTRY erroneamente.

Ajustado make_shutdown_plan para admitir:
- MCP adotado/orfao com origem ausente, ja previsto; ou
- MCP filho da GUI identificada, com criacao nao anterior a GUI.
Qualquer outro pai continua recusado; multiplex de papeis
e conflitos de criacao continuam bloqueados.

Testes especificos PASS, incluindo pai inesperado recusado.
Reensaio externo na maquina atual: SHUTDOWN_PLAN_ONLY,
4 papeis e identity_digest reproduzivel.
O resultado continua sendo somente proposta read-only,
execute=false, signals_sent=false, safe_to_apply_installer=false.
P9-B aberta ate recuperador real supervisionado e poststart.
