# P9-B ? Backend experimental de rollback HKCU e atalhos

Estado: IMPLEMENTADO COM INTERFACE DE REGISTRO INJETADA;
NAO HABILITADO PARA PRODUCAO.

O modulo installer/rag_p9b_windows_restore_backend.py aceita
um adaptador de registro injetado, e por padrao nao cria
um adaptador winreg real. Exige flags explicitas de execucao,
prova de parada, canal externo e journal. Primeiro captura
estado anterior e confere o backup, depois aplica os 5
atalhos e 2 chaves HKCU dentro do escopo aprovado.
Em falhas, tenta restaurar o estado lido antes do primeiro
sinal, compara registro e links apos a compensacao e
marca SHELL_BACKEND_RECOVERY_REVIEW_REQUIRED,
com compensation_verified e eventuais erros.
Sucesso de escrita retorna POSTVERIFY_REQUIRED, nunca
verified=true: a verificacao independente deve ser separada.

Seis testes sinteticos PASS, incluindo falha no registro,
copia de compensacao, backup corrompido, falta de canal
externo e alvo symlink.

LIMITACOES: nao existe transacao atomica entre sistema de
arquivos e registro; eventual falha de energia ou morte do
processo requer journal persistente + supervisor externo.
Ainda NAO existe adaptador winreg real aprovado, nem foi
aplicada restauracao na maquina em uso. O NSIS segue bloqueado.


## Ensaios integrados do adaptador e journal

tests/test_rag_p9b_windows_backend_integrated.py executou
backend + adaptador fake winreg + journal fsync em diret?rios
descartaveis. Comprovou restaura??o dos bytes de atalho em
scratch e journal de 2 etapas; segundo teste recusou
journal j? existente antes de muta??o.
Resultado continua APPLIED_POSTVERIFY_REQUIRED, nunca verified.
Nenhuma opera??o de escrita em HKCU real foi executada.
