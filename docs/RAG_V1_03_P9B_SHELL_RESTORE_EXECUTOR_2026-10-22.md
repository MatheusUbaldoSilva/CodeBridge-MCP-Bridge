# P9-B ? Executor de recuperacao do shell (contrato)

Estado: BACKEND INJETAVEL EM TESTES; NENHUMA RESTAURACAO REAL.

Arquivos:
- installer/rag_p9b_shell_restore_executor.py
- tests/test_rag_p9b_shell_restore_executor.py

Antes de aceitar uma restauracao, exige prova de processos parados,
canal independente, flag execute, journal, plano de backup validado
por hash e backend dedicado mais verificacao posterior independente.
Nao inclui um backend real do Windows nesta fase. Se backend
ou verificacao nao estiverem presentes a operacao e recusada.
Excecoes/retorno incompleto geram SHELL_RESTORE_REVIEW_REQUIRED
sem alegacao de sucesso. 7 testes isolados PASS.

IMPORTANTE: este contrato nao e um mecanismo atomico de HKCU+arquivos
e nem comprova rollback total do NSIS. A implementacao concreta
ainda necessita auditoria de estado anterior, tratamento de erros
parciais e prova pos-restauracao. Nao usar para recuperar producao
antes desses requisitos.
