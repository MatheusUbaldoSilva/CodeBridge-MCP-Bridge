# P9-B ? Gate read-only de execucao supervisionada

Modulo: installer/rag_p9b_transaction_execution_gate.py
Exige identidade do manifesto de quatro artefatos validada
diretamente por SHA256, prova independente de parada completa
e aus?ncia de journal pendente. Mesmo com provas positivas,
nao autoriza NSIS, HKCU, alteracoes de arquivos ou restart.

Teste real com CodeBridge ativo:
P9B_EXECUTION_GATE_REFUSED
reason=INDEPENDENT_POSTSTOP_UNVERIFIED
nsis_executed=false; installed_modified=false.
Quatro testes unitarios PASS.

Corrigida a transcricao do SHA256 na documentacao do manifesto:
b358a28a0329bb563187a7c36f86331600ca11b1518a601484f9569fef7527f1
Confirmado pelo calculo direto do arquivo Windows.

A fase continua aberta ate existir um executor elevado
independente com rollback de producao, verificacao depois
da restauracao e handshake publico MCP.
