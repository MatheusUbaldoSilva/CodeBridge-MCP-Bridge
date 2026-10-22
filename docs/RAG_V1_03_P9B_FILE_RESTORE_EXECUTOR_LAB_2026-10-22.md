# P9-B ? Executor de rollback de arquivos em laboratorio

Modulo installer/rag_p9b_file_restore_executor_lab.py.
Confere ZIP e SHA256 original do backup, validade do escopo,
symlinks e conteudo exato dos 22 destinos artificiais ANTES
de modificar qualquer arquivo da pasta descartavel.
Restaura os 236 anteriores, remove apenas destinos que possuem
marcador exclusivo do laboratorio e verifica os hashes finais.

Ensaio real com backup NSIS: FILE_RESTORE_LAB_VERIFIED;
236 arquivos anteriores restaurados; 22 destinos novos
removidos; production_modified=false; nsis_executed=false.
Quatro testes unitarios PASS com recusas por alteracoes
nao reconhecidas, ZIP adulterado e destino de producao.

Isto NAO e executor de producao; nao altera registro HKCU,
atalhos reais, servicos nem executa NSIS. Falta o supervisor
real independente com recuperacao completa e reconexao publica.
