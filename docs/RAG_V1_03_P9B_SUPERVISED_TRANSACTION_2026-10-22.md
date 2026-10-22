# P9-B ? Contrato de transacao supervisionada

Criado installer/rag_p9b_supervised_transaction.py, com
assess_transaction e rehearse_transaction. Somente interfaces
injetadas de laboratorio (sem NSIS e sem desligamento real).
Exige provas de backup, preimagem, canal externo e pos-parada.

Recusa UNIFIED_LAB_RECOVERED como prova de rollback
de producao. Mesmo uma prova sintetica
PRODUCTION_ROLLBACK_VERIFIED retorna
TRANSACTION_GATES_OBSERVED_ONLY, authorized=false:
o executor elevado deve revalidar os controles.

Seis testes direcionados PASS, incluindo fluxo completo
de laboratorio, falha de parada, rollback nao verificado
e canal independente ausente.
Nenhuma instalacao ou indice RAG foi alterado.
