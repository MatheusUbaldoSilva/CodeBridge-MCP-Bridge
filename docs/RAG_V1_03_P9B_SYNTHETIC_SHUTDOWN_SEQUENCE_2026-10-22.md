# P9-B ? Ordem de parada isolada

Data: 2026-10-22
Estado: APENAS SIMULACAO. P9-B ABERTA.

Arquivos:
installer/rag_p9b_shutdown_sequence.py
tests/test_rag_p9b_shutdown_sequence.py

A rotina exige controller.fake com simulation_only=True e
simulate=True explicito. Sua API NAO controla processos reais,
nao envia signals ou mensagens Win32 e nao instala pacotes.

Ordem ensaiada: GUI -> MCP -> ADAPTER -> TUNNEL.
Cada etapa recebe identidade pid + create_time da proposta atual.
Se o controller rejeitar uma etapa, as posteriores nao sao invocadas.
Plano incompleto, topologia ambigua e controller real sao recusados.
Suite sintetica: 5 testes PASS.

Nao confundir SIMULATED_SEQUENCE_PASS com evidencia de parada real.
Segue faltando desenvolver e testar executor independente com fechamento
gracioso e valida??o posterior, e somente depois decidir cutover
NSIS supervisionado com snapshot correspondente.
