# P9-B ? Contrato de transacao NSIS

Estado: PLANEJADO E TESTADO; update oficial NAO EXECUTADO.

A rotina installer/rag_p9b_nsis_transaction_plan.py valida
somente leitura o mesmo commit de origem, identidade de pacote
e snapshot, prova de parada de GUI/MCP, ausencia de processos,
canal de recuperacao independente e guard oficial sem bloqueadores.

Se todas as condicoes forem observadas, retorna
P9B_TRANSACTION_STEPS_OBSERVED_ONLY e authorized=false.
O modulo NAO chama NSIS, nao modifica arquivos, nao restaura
nem altera a fila RAG. Em caso de inconsistencias retorna
P9B_TRANSACTION_REFUSED.

Sequencia contratada:
1. Revalidar SHA256 de pacote e backup e guard NSIS
2. Iniciar instalacao somente sob controlador externo com journal
3. Verificar codigo de saida e arquivos instalados
4. Recuperar GUI, adapter, MCP e tunnel
5. Exigir handshake publico real
6. Se falhar, abortar e usar plano seguro de restauracao

Restricao relevante: o snapshot atual protege os arquivos
sobrescritos pelo NSIS, mas a reversao total requer cobrir tambem
atalhos, registro e artefatos de bootstrap. Nao tratar ensaio de
restauracao de arquivos como rollback integral provado.
Sete testes sinteticos de gates foram aprovados.
