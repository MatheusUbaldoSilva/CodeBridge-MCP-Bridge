# P3 ? Divergencia de escopo no gate de ensaio supervisionado

Data: 2026-10-21. Auditoria estatica, somente leitura dos componentes do RAG instalado.

O gate rag/runtime/production_supervised_trial.py contem lista fixa _ALLOWED_ADDED = ('rag/runtime/live_integrity.py',) e _ALLOWED_CHANGED com arquivos de outro ensaio. A candidata incremental realmente construida em P1/P2 acrescenta apenas rag/runtime/incremental_scheduler_gate.py, SHA256 da fonte 6d0e790e82ee9bea7f163cf0b5244accc794a87bf6032d97144f73ab21c3feed, com delta de 1 documento e 2 chunks. Nao se pode assumir que a evidencia do gate anterior aprova essa candidata.

Os requisitos de fonte da candidata atual devem ser derivados de manifesto e proveniencia SHA por commit, sob travas e com aprovacao explicita para a geracao de destino. Ate que haja implementacao e testes isolados desta integracao, preservar _ALLOWED_ADDED, as demais travas e os bloqueadores. O gate supervisionado ainda exige provas separadas do leitor MCP, da identidade da geracao, da reversibilidade no Windows, da aprovacao operacional, da janela de tempo e da ausencia de pointer/journal pendentes. Nao inserir strings de autorizacao artificiais nem chamar publicador de producao.

Este documento nao concede ativacao; geracao publica legacy 210 documentos continua intacta e candidata 211 documentos permanece isolada.
