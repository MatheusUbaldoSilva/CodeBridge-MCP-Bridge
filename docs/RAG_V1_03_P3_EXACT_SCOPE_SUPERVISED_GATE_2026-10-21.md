# P3 ? Verificacao exata de fonte no gate supervisionado

2026-10-21. O gate `assess_supervised_trial` agora exige `approved_source_sha256` explicito, validado pelo verificador `inspect_approved_source_scope`, com o fingerprint exato da revisao de fontes derivado do bundle. Um unico caminho ou hash omitido bloqueia o ensaio com `EXACT_SOURCE_SCOPE_NOT_ATTESTED`.

A regra nova e adicional: a allowlist antiga `_ALLOWED_ADDED` e `_ALLOWED_CHANGED` permanece inalterada, junto de todos os bloqueadores de publicacao, provas MCP e rollback. A verificacao `SCOPE_MATCHED_NOT_AUTHORIZED` jamais e autorizacao de cutover por si so.

A fixture de teste existente foi atualizada com hashes artificiais *apenas* no teste; um teste negativo remove hash e comprova BLOCKED. Nenhum token real de operador foi emitido, nenhum pointer ou geracao publica foi escrito. O candidato incremental atual ainda nao atende automaticamente a allowlist historica; o bloqueio de producao permanece.
