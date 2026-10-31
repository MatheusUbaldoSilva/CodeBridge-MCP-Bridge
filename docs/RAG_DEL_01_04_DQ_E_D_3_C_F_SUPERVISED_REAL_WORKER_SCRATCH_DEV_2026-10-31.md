# RAG-DEL-01.04-DQ-E-D-3C-F — Protocolo pinado supervisionado no entrypoint real (DEV)

## Implementacao
- rag/runtime/isolated_project_worker.py: novo modo exclusivamente de laboratorio --pinned-scratch-supervised com TEMP-root e parent-pid, sem fallback para a busca legada e sem carga de modelos ou Qdrant. O modo legado sem flags nao foi alterado.
- knowledge_deletion_liveness_child_lab.py: a rotina supervisionada agora e chamada pelo entrypoint real do worker. Mantem um handle Win32 aberto para o objeto do pai durante toda a sessao, validado via GetExitCodeProcess. O handle nao muda de alvo se o PID for reutilizado posteriormente; fecha o handle na saida, inclusive em erros. Mantem a verificacao do pipe e limites de tempo do protocolo.
- knowledge_deletion_liveness_parent_lab.py: o pai passa a iniciar o entrypoint real em modo supervisionado e a comparar o esquema EXATO do resultado: estado, projeto, geracao, nonce, request SHA256, tree SHA256 e flags de autorizacao falsas. Qualquer campo extra, ausente ou divergente falha fechado.
- A hierarquia mantida pelo pai continua generation(shared) -> semantic(exclusive) -> mutex catalog, sem reacquisicao pelo filho. O hash dos arquivos vetoriais e o manifesto/catalogo/SQLite sao revalidados em TEMP. O processo permanece sintetico e reversivel.

## Evidencias
- 5 novos testes em tests/test_rag_del_01_04_dqed3ce2_liveness_parent_child_lab.py: entrypoint supervisionado sem resolver indice nem chamar modelo, CLI invalida, recusa de respostas antigas/forjadas por nonce/projeto/geracao/hash/flags, journal ROLLED_BACK surgindo durante a sessao e alteracao do catalogo antes do ACK.
- Suite integrada pai/filho: 13 testes PASS, incluindo kill do pai, kill do filho, timeout, resposta boa, vetor alterado e writer Win32 concorrente.
- Regressao RAG-DEL: 430 executados, 424 PASS, 6 SKIP, zero falhas.
- Regressao RAG-AUTO sem MCP: 241 executados, 236 PASS, 5 SKIP, zero falhas.
- Total: 671 executados, 660 PASS, 11 SKIP, zero falhas.

## Limites de seguranca e pendencias
O handle Win32 evita que observacoes futuras de liveness migrem para um PID reutilizado. A identificacao inicial do pai nao e autenticacao criptografica do canal; o nonce e hash de requisicao correlacionam mensagens mas nao previnem reutilizacao de uma requisicao em outras sessoes sem um mecanismo adicional. Este modo nao prova uma operacao Qdrant transacional nem inferencia com modelo real. Nenhum processo instalado foi atestado; a fila READY_FOR_REVIEW e a reconciliacao de journals seguem bloqueadores, assim como a falta de generation_probe no MCP conectado.

Proximo marco sugerido: DQ-E-D-3C-G (auditoria de replay, autenticacao de sessao e integracao do worker com stub multiprocessos mais rigorosa), sempre DEV antes de qualquer proposta de promocao. Sem Stable, catalogo/indice real, fila real, exclusao operacional ou push GitHub.