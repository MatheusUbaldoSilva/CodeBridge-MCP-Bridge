# P3 ? Ponteiro conflitante recusa rollback pendente

Data 2026-10-21. Teste real da funcao rollback_pending_to_legacy com arquivo de controle em fixture isolada. Journal PREPARED nomeia um candidato, mas ponteiro existente aponta para outra geracao valida. A rotina rejeita com 'pointer conflicts with pending journal', preserva integralmente os bytes do journal e ponteiro e nao apaga a candidata. Nenhuma escrita no RAG publico, teste nao autoriza cutover ou rollback real.

Valida somente bloqueio de divergencia de identidades apos a gravacao; nao comprova completa prontidao de publicacao.
