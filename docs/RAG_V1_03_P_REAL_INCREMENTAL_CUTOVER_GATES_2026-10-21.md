# RAG V1.03-P ? Sequencia curta para destravar indexacao incremental real

Data: 2026-10-21 | base `0f40ce7` | planejamento, nenhuma publicacao

## Evidencia congelada

- MCP instalado pid 5936: leitor protegido e serializacao de semantica observados. Tres consultas HYBRID concorrentes PASS. Cross-store legacy `OBSERVED_CONSISTENT`, 210 documentos, 8761 chunks.
- O preflight `rag/runtime/incremental_preflight.py` devolve bloqueadores fixos, independentemente dessas provas; `safe_to_publish=False`.
- `rag/runtime/production_cutover_gate.py::assess_real_cutover` devolve `safe_to_activate=False` por contrato e exige baseline e candidato versionados, hash/freshness/manifest delta e evidencias externas.
- `rag/runtime/production_generation_transition.py` possui escritor de pointer com journal, mas nao deve ser chamado sem candidato fechado, atestado de leitores e autorizacao do operador para geracao especifica.

## Sequencia dividir para conquistar

**P1 ? Preparar candidatos fechados somente em staging isolado.** Fonte aprovada individualmente por path, hash e commit; um snapshot de baseline fechado; geracao candidata completa com SQLite, manifesto e Qdrant. Provar que nenhum arquivo publico muda; nunca copiar Qdrant aberto sem protocolo comprovado.

**P2 ? Verificar candidato de ponta a ponta.** Validador do bundle, integridade SQLite e identidades dos vetores, freshness contra commit atual, relatorio de delta de documentos/chunks, sem perda de fontes existentes. Testar rejeicao de origem alterada e rollback isolado.

**P3 ? Fechar precondicoes do corte sem ativar.** Teste de lock compartilhado/exclusivo com writer e leitores MCP carregados, journal recuperavel e versao fixada; integrar sinais auditaveis nos gates em vez de remover bloqueadores fixos. Preservar `activation_authorized=False` ate autorizacao explicita do operador.

**P4 ? Corte controlado com autorizacao futura.** Somente quando P1-P3 comprovados e operador aprovar identificador de geracao, fazer plano de rollback, janela supervisionada, prova pos-troca das consultas MCP e hash de legado preservado. Sem aprovacao, terminar em `GO-LIVE BLOCKED`.

## Proximo alvo de implementacao

P1 deve usar as capacidades de stage existentes sem tocar no indice publico. O indice atual e antigo; a fonte candidata de prova pode ser `rag/runtime/incremental_scheduler_gate.py` somente depois de aprovacao explicita para indexar esse arquivo. Nao iniciar scheduler, worker, indexacao ativa ou promocao de generation nesta fase.
