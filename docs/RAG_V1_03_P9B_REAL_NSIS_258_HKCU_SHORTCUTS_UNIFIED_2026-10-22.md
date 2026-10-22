# P9-B ? Ensaio unificado NSIS verdadeiro, 258 arquivos, HKCU e atalhos

Teste reproduzivel: tests/test_rag_p9b_full_scope_actual_hkcu_integration.py

Ambiente Windows DESCARTAVEL: 236 arquivos originais extraidos
do backup oficial, mais 22 destinos novos. O NSIS verdadeiro
de laboratorio e compilado localmente para sobrescrever os
22 novos e primeiro antigo com sentinela, pausar 15 segundos
e permitir encerramento forcado do instalador.
A interrupcao e explicitamente registrada no journal.

No mesmo ciclo de testes, o backend de recuperacao existente
restaura os 236 arquivos e remove os 22 novos, reconstitui
cinco atalhos de laboratorio e duas chaves HKCU temporarias
usando winreg REAL, ScopedHKCU com facade remapeada para
Software/CodeBridgeP9BLab/<UUID> (nao acessa producao).
O posverificador confere os hashes de todos os arquivos e
o estado de HKCU/atalhos. Journal inclui sete eventos no caso
NSIS interrompido, com fsync. Todos os 3 testes PASS:
unificado real NSIS, integrado sem NSIS e recusa de arquivo
estranho antes do rollback do shell.

IMPORTANTE: o recuperador unificado roda sob o processo de
testes, nao em supervisor destacado; a alteracao de HKCU
foi injetada pelo harness, nao pelo instalador NSIS oficial.
A operacao nao demonstra isolamento do executor elevado ou
seguranca da atualizacao em producao. P9-B continua ABERTA.
