# RAG-LAB.01-E - Janelas de amostragem (2026-10-17)

Estado: CONCLUIDO EM LABORATORIO. Nao autoriza backup real.

## Implementacao
- rag/runtime/offline_process_sampling_gate.py: avalia series de observacoes CIM por PIDs sinteticos conhecidos, com amostras UTC validas, duracao maxima por consulta, intervalo maximo entre consultas, idade maxima do ultimo resultado e relogio de verificacao explicito.
- Exige que TODOS os PIDs do escopo tenham sido observados ativos antes da comprovacao de saida e que existam duas amostras FINAIS consecutivas sem nenhum deles.
- Bloqueia identidade alterada, reaparicao de PID, dados incompletos, observacao antiga, amostra futura e consultas com timeout ou lacunas.
- Integra testes/test_offline_windows_scoped_family.py com o ensaio real sintetico do Windows.
- Nova suite tests/test_offline_process_sampling_gate.py: 13 testes.

## Validacao
- Testes focados: 13 e Windows scoped 1 OK.
- Regressao: 83 generation + 176 offline + 7 preflight + 38 incremental = 304 testes OK, exit 0.
- Invariantes: copy_authorized=false, all_handles_closed=false, production_quiescence_proven=false.
- A prova observa somente PIDs explicitamente informados; nao comprova discovery global, mmap e todos os handles de producao.

## Proxima fase
RAG-LAB.01-F - races e cobertura negativa do inventario, incluindo processo que desaparece durante CIM, credenciais insuficientes, identidades invalidas e PID reutilizado.
