# P3 ? Revisor de escopo exato, sem autorizacao de ativacao

2026-10-21. O novo rag/runtime/production_source_scope_attestation.py compara exclusivamente em memoria uma revisao de fontes fechadas com mapa explicito de caminhos e SHA256 e fingerprint da revisao. Rejeita fonte inesperada, removida, digests divergentes, duplicatas e dados invalidos. Correspondencia exata retorna SCOPE_MATCHED_NOT_AUTHORIZED, activation_authorized=false e safe_to_publish=false.

O revisor NAO esta ligado ao publicador real, nao autentica a aprovacao humana, nao altera o gate supervisionado legado e nao escreve SQLite, manifesto, Qdrant, journal ou pointer. A integracao real dependera de aprovacoes verificadas individualmente, revisao do escopo da geracao e consentimento novo para qualquer publicacao.

Testes: 6 de escopo + 320 incrementais + 64 do instalador PASS. Candidato publico permanece GO_LIVE_BLOCKED.

Integracao posterior: tests/test_production_source_scope_real_review_isolated.py (2 PASS) cria pares de bundles fechados sinteticos e chama summarize_versioned_source_review verdadeiro. Aceita apenas o digest da fonte nova e rejeita hash diferente e modificacao adicional nao listada. Nao usa nem publica a base instalada.
