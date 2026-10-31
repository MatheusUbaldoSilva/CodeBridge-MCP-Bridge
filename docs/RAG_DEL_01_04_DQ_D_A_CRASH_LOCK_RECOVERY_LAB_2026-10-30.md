# RAG-DEL-01.04-DQ-D-A — Queda de leitor e locks em laboratorio

Testes multiprocessos Win32 de uma sessao privada TEMP-only com generation shared, semantic exclusive e catalog mutex. Um processo de laboratorio mantem os tres locks; o processo observador confirma recusa de generation exclusive, semantic exclusive e catalog lock dentro de prazo. Apos encerrar o subprocesso de teste abruptamente, todos os locks podem ser obtidos novamente, sem modificacao do SQLite, manifesto ou catalogo.

Um segundo teste simula journal de exclusao pendente e confirma recusa de leitura nova, sem executar rollback automatico ou apagar journal.

A primeira execucao identificou erro no proprio fixture: sqlite3.connect usado como context manager nao fecha automaticamente o handle no Windows. O fixture foi ajustado para contextlib.closing e os dois testes passaram.

Regressao: RAG-DEL 339 (335 PASS/4 SKIP), RAG-AUTO sem MCP 241 (236 PASS/5 SKIP), zero falhas.

Limites: somente arquivos em TemporaryDirectory, sem workers instalados, exclusao real, Stable, push ou atuacao sobre catalogo operacional. DQ-D-B deve certificar rollback/CAS com concorrencia real; DQ-E depende de atestacao do MCP instalado.