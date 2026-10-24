# CodeBridge RAG — prioridade leitura, escrita e anexos
P9-B/NSIS suspenso; checkpoint 973861f preservado. Nao alterar RAG ativo.
Baseline: READY, 211 documentos, 8774 chunks, indice de 2026-10-09.
RAG-RW.01: anexar fonte individual/multipla, validar hash, escopo e aprovacao.
RAG-RW.02: escrita incremental isolada, deduplicacao e remocao.
RAG-RW.03: geracao SQLite/Qdrant/manifest atomica; leitores MCP fixados; rollback.
RAG-RW.04: UI de fontes, status, atualizacao, exclusao e pesquisa com citacoes.
RAG-RW.05: benchmark de relevancia; prova E2E inserir, buscar, editar, remover, reiniciar e recuperar.
A UI existente so faz previa de pasta; publicacao incremental nao liberada. ChatGPT upload nao aparece automaticamente no Windows.
Gates: testar isoladamente; diffs e commits revisados; nao tocar 3 arquivos historicos sujos; nao executar NSIS.
