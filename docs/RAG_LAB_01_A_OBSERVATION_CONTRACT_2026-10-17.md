# RAG-LAB.01-A - Contrato das amostras Windows (2026-10-17)

Estado: CONCLUIDO EM LABORATORIO; nao autoriza producao.

## Alteracoes
- Novo rag/runtime/offline_process_sample_contract.py valida a origem WINDOWS_CIM_LAB_SCOPED, escopo de PIDs imutavel, tempos UTC ordenados, identidades completas PID/PPID/creation time/SHA-256, duplicatas e inventarios falhos.
- Novo tests/test_offline_process_sample_contract.py, 11 testes de contrato.
- Invariantes: copy_authorized=false; all_handles_closed=false; production_quiescence_proven=false.

## Validacao
- Testes focados: 11 PASS.
- Regressao: 83 generation + 142 offline + 7 preflight + 38 incremental = 270 PASS.
- O contrato nao autentica por si so a origem das amostras e nao prova parada global.

## Proxima letra
RAG-LAB.01-B: observador CIM reutilizavel em processo separado, com inicio/fim da observacao e saida sanitizada. Somente fixtures e PIDs sintéticos.
