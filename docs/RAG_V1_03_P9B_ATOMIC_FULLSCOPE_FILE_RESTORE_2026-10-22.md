# P9-B ? Rollback atomico de arquivos de laboratorio

O restaurador installer/rag_p9b_file_restore_executor_lab.py
nao grava mais os bytes antigos diretamente em arquivo final.
Agora escreve arquivo temporario no MESMO diretorio, confirma
fsync, revalida destino e substitui usando os.replace, removendo
arquivos temporarios em caso de erro.

Teste novo injeta falha no os.replace e prova:
- arquivo anterior nao sofre truncamento/parcialidade;
- destino novo nao e removido sem rollback antigo;
- arquivo temporario e descartado;
- retorno de recuperacao e REFUSED, nao sucesso falso.

Isto melhora o lab com 236 originais + 22 novos.
Nao garante atomicidade entre TODOS os arquivos, registro e
atalhos; ainda precisa journal externo e recovery idempotente
apos interrupcao verdadeira do proprio recuperador.
