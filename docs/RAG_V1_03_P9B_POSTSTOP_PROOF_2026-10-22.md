# P9-B ? Prova independente de p?s-parada

Data: 2026-10-22
Estado: AINDA NAO PARADO, SEM INSTALACAO NSIS.

Criado installer/rag_p9b_poststop_verification.py
e tests/test_rag_p9b_poststop_verification.py

O contrato exige inventario sem processos CodeBridge, sem linha de
comando opaca, guard oficial sem bloqueadores e portas MCP 8765 e 8767
sem listener. Mesmo um resultado POSTSTOP_OBSERVED_ONLY e SOMENTE
evidencia, nunca autoriza a instalacao (CLI sempre exit 2).
Verifica em modo leitura e nao envia sinais, nao encerra servicos.

Ensaio sint?tico: 7 testes PASS.
Prova real independente por Remote Desktop:
POSTSTOP_UNVERIFIED / CODEBRIDGE_PROCESSES_STILL_RUNNING.
GUI 1376, MCP 9300, adapter 10768 e tunnel 5608 ativos.
Nenhum encerramento nem modificacao do indice foi realizado.

Ultima etapa antes do cutover real ainda requer executor
independente de parada graciosa com revalidacao de PID+create_time
e recuperacao assegurada. NAO executar preview NSIS enquanto o
guard oficial bloquear. Preservar backup/manifesto correspondente.
