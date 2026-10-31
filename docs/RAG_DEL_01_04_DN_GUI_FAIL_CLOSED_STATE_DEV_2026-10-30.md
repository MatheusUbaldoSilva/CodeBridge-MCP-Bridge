# RAG-DEL-01.04-DN — Estado da GUI em falha de leitura (DEV)

## Critérios verificados

Novos testes Qt em test_rag_del_01_04_dn_gui_busy_state.py exercitam, sem modelo, sem ponteiro real e sem backend de exclusão:

1. Após uma listagem pública válida, erro posterior de generation busy mantém a lista anterior e não ativa o seletor de exclusão pública.
2. Ao trocar do projeto público para outro projeto, a GUI zera os itens antes de despachar a consulta. Se o catálogo privado fica ocupado, não exibe arquivos antigos na visão do novo projeto.
3. Erros de transição da geração pública não criam seleção de arquivos apagáveis e mantêm o botão de revisão de exclusão desabilitado.

Todos os três testes passaram usando Qt offscreen. Nenhuma mudança em app_rewrite/rag_panel.py foi necessária além do commit seletivo DL já encerrado.

## Limites de segurança

A permanência da lista no mesmo projeto quando um refresh falha é um comportamento de leitura, não constitui prova de frescor para decisões destrutivas. O índice público jamais é excluível; o privado só permite prévia, e seu inventário operacional ainda aguarda a formalização de locks e de pin de catálogo. O módulo DM permanece estritamente restrito ao laboratório.