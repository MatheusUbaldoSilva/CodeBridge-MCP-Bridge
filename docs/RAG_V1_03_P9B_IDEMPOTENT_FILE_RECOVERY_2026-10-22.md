# P9-B ? Recuperacao reiniciavel de arquivos NSIS em lab

Agora o restaurador de arquivos pode ser invocado novamente
apos interrupcao do proprio rollback. A ausencia de um
destino NOVO ja removido e aceita como progresso valido;
arquivos ainda existentes precisam conter exatamente a
sentinela de laboratorio autorizada. Bytes estrangeiros
continuam recusados antes de novas modificacoes.

O restaurador de arquivos antigos usa escrita atomica
(fsync + os.replace), e os alvos novos sao removidos de
forma idempotente usando missing_ok. O estado final e
validado com hashes de 236 anteriores e ausencia de 22
destinos novos no ensaio com backup real.

Novos testes: executar rollback duas vezes; iniciar com
destino novo ja removido. Teste de arquivo estrangeiro
preexistente permanece ativo. Esta tolerancia NAO autoriza
rollback em producao; esta restrita ao laboratorio.
