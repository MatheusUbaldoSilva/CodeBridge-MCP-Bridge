# P9-B ? Journal duravel de rollback

Criado installer/rag_p9b_rollback_journal.py para
registro append-only de etapas SHELL_*, escrita com
flush e fsync apos cada evento.
E recusada a reutilizacao de um journal existente.
Leitura independente retorna sequencia, quantidade
e ultimo estado, sem expor valores de registro ou
conteudo dos atalhos. Detalhes sao filtrados por
whitelist para nao registrar credenciais.

Quatro testes PASS, inclusive reuso bloqueado,
sequencia corrompida e dados nao autorizados ausentes.
Nao foi iniciado NSIS ou restauracao real.
A persistencia de cada evento no disco nao substitui
orquestracao externa nem transacao atomica HKCU+arquivos.
