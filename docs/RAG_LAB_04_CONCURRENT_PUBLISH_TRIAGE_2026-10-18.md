# RAG-LAB.04 — Triagem de teste de publicacao concorrente (18/10/2026)

Teste: tests/test_generation_backup_publish_process_race.py.

Ocorrencia: na primeira bateria integrada de 394 testes, o caso test_two_publishers_only_one_activates falhou. Ambos os processos retornaram erro (RecoveryCandidateError e TransitionRecoveryError), quando exatamente um deveria publicar. Nao houve alteracao no codigo de publicacao durante esse teste.

Reproducao: execucao focada imediatamente seguinte PASS. Regressoes integradas repetidas: 394 PASS (266 offline + 83 generation + 7 preflight + 38 incremental). Nova serie de 8 execucoes independentes do teste focado: 8 PASS, 0 FAIL.

Conclusao: anomalia intermitente observada uma vez, causa ainda nao demonstrada. Nao modificar thresholds, ignorar erro ou afirmar correcao. Se reaparecer, instrumentar razoes encadeadas e estado do journal em fixture descartavel para estabelecer causa.

Escopo exclusivamente sintetico. Nenhum backup ou parada de producao executados.
production_backup=BLOCKED
