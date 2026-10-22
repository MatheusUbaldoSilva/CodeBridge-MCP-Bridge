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


## Teste integrado e backup real

Criado installer/rag_p9b_shell_restore_scratch_backend.py,
backend INUTILIZAVEL EM PRODUCAO, limitado a pasta scratch.
Possui verificador de arquivos por sha256 e registro JSON.
O controlador foi executado no snapshot verdadeiro:
NSIS_SHELL_REGISTRY_SHORTCUT_SNAPSHOT.zip
e escreveu apenas SHELL_TRANSACTION_SCRATCH.
JOURNAL: SHELL_RESTORE_ARMED -> SHELL_RESTORE_VERIFIED.
Resultado local restaurado=true aplica-se EXCLUSIVAMENTE a scratch,
e registry_modified=false/shortcuts_modified=false referem-se
ao registro e atalhos reais do Windows.
Duas provas integradas sinteticas PASS.
Ainda NAO existe backend Windows aprovado para rollback ao vivo.
