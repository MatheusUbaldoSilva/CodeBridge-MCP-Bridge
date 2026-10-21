# RAG V1.03-F ? recuperacao sintetica de crash e fencing

Data: 2026-10-21. Base: `735099e`.

Teste dedicado cria somente processo Python filho pertencente ao proprio ensaio e banco SQLite de fixture em diretorio temporario. Filho adquire `SupervisorLock`, emite primeira geracao e aguarda. Processo pai confirma disputa bloqueada e encerra **apenas o PID sintetico criado pelo teste**. Windows libera o lock apos a saida do filho; novo processo proprietario emite geracao posterior, que invalida a antiga. O teste nao para processos reais do CodeBridge.

A prova e somente de fixture Windows e mecanismo cooperativo. Nao comprova shutdown geral de GUI/MCP, ausencia global de mappings nem ativacao segura de worker ou scheduler. Nenhuma fonte RAG publica e modificada ou publicada.
