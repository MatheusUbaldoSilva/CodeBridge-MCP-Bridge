# RAG V1.03 P3 ? Lock Windows real entre processos isolados

Data: 2026-10-21. Apenas diretorios temporarios; nenhuma escrita no RAG instalado.

Dois novos testes test_p3_real_windows_generation_lock_isolated.py executaram Python filho independente utilizando o verdadeiro production_generation_lock baseado em LockFileEx:
- Com o lock compartilhado do leitor retido no processo pai, processo filho com exclusivo falha fechado (BUSY_CONFIRMED); apos liberacao, passa a ACQUIRED.
- Com o lock exclusivo do escritor retido no processo pai, processo filho leitor compartilhado falha fechado; apos liberacao, passa a ACQUIRED.

Ambos PASS, Windows real e processos diferentes. Raiz fake temporaria CodeBridge/rag, sem patch do mecanismo Win32: somente resolve_rag_sqlite_path foi apontado para a fixture. Nao foi feito publish, corte real, restart ou transicao da geracao publica.

Limites: prova sincronizacao do byte lock, mas nao demonstra atomicidade de todas as etapas da publicacao ou configuracao completa do MCP instalado. GO_LIVE_BLOCKED ate plano de corte verificado e autorizacao especifica.
