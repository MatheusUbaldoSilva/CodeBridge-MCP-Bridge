# P9-B ? Plano de parada supervisionada sem execucao

Data: 2026-10-22
Status: SHUTDOWN_PLAN_ONLY, P9-B permanece aberta.

Fonte: installer/rag_p9b_supervised_shutdown_plan.py
Testes: tests/test_rag_p9b_supervised_shutdown_plan.py

O planejamento exige exatamente GUI MCP adapter tunnel e
identidade PID mais create_time verificavel. Recusa anomalia
de quantidade de processos, conflito cronologico ou origem
inesperada do MCP. Gera digest SHA256 da identidade ordenada.
Nenhum processo e encerrado. O CLI retorna sempre codigo 2
para nao ser interpretado como permissao de update pelo NSIS.

Prova real pelo MCP e canal independente Remote Desktop:
state=SHUTDOWN_PLAN_ONLY
digest=d4619033de2623a847c54bff48a2c0aca0ba9f0b3a2911e6d748dcd1ba515b44
GUI 1376, MCP 9300, adapter 10768, tunnel 5608.
Prova de correspondencia do hash em dois ambientes independentes;
diferencas na quantidade de processos opacos sao esperadas e nao
alteram a identidade da stack CodeBridge.
Versao instalada e indice publico nao foram alterados.
Nao ha ainda executor operacional de parada/relancamento aprovado.
Nao usar este digest em outra janela sem atualizar a identidade.

Gate de instalacao oficial permanece UPDATE_PROCESS_BLOCKED.
A proxima fase necessita encerramento controlado real fora do MCP,
verificacao oficial de processo ausente, update NSIS com snapshot exato,
rollback e recuperacao por canal independente.
