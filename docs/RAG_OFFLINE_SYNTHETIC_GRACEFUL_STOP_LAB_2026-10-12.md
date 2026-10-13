# RAG   Teste de encerramento gracioso de processo sintético
Estado: LABORATÓRIO; NENHUMA OPERAÇÃO EM PRODUÇÃO.

`rag.runtime.offline_synthetic_stop_trial.run_synthetic_stop_trial` lança
exclusivamente um filho Python criado pelo próprio ensaio. O processo filho
abre para escrita o SQLite de uma fixture sintética e responde por stdin ao
sinal `GRACEFUL_STOP`. Enquanto aberto, a guarda Windows de leitura sem
compartilhamento para escrita deve recusar acesso; após a saída limpa,
a guarda precisa adquirir o handle. Nenhum processo do CodeBridge é parado.

Falhas de inicialização, ausência de SQLite ou raiz incorreta bloqueiam.
A rotina só pode eliminar forçosamente o processo filho que ela mesma iniciou
se houver falha na limpeza; nunca atua sobre processos existentes.
O sucesso `LAB_CHILD_GRACEFULLY_STOPPED` não prova encerramento da GUI/MCP,
de índices Qdrant, cache mmap, bancos SQLite de produção ou adaptadores.
Os resultados incluem `copy_authorized=false`.

Aprovação e execução de manutenção no ambiente real continuam pendentes.

Extensão: o filho agora mantém simultaneamente handles de SQLite, manifesto e um arquivo Qdrant sintéticos. A ausência de qualquer armazenamento bloqueia antes de iniciar o filho.

Execução autônoma: python rag_offline_synthetic_stop_cli.py --fixture-root RAIZ_SINTETICA --lab-only. Código 0 significa apenas que o ensaio sintético passou; copy_authorized permanece false.

A prova em laboratório também exige SHA-256 inalterado dos três arquivos amostrados antes e após o encerramento do filho, além de não interromper um processo sintético não relacionado.
