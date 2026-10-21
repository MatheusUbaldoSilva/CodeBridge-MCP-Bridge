# RAG V1.03 P1 ? Fonte autorizada indexada em laboratorio isolado

Data: 2026-10-21. Commit de partida: `515d9e68d162d5949049c9c4f33aca516b48cbdc`.

Autorizacao especifica do operador limitada a `rag/runtime/incremental_scheduler_gate.py` e exclusivamente a geracao isolada, sem publicacao ou ativacao automatica. SHA256 decodificado revalidado antes de indexar: `6d0e790e82ee9bea7f163cf0b5244accc794a87bf6032d97144f73ab21c3feed`. Fonte versionada, sem dirty.

Para impedir staging na arvore ativa, `build_staged_index` ganhou argumento opcional `isolated_staging_parent` com verificacao de fronteira; o caminho legado sem o argumento fica inalterado. A rotina real gerou um novo bundle fora do RAG publico em:

`C:\Users\Matheus\AppData\Local\Temp\codebridge-rag-p1-isolated\build-f836f40ee74b42ce9ba1b6334efb96be`

Resultado: `STAGED_NOT_PUBLISHED`, um documento CODE, 2 chunks, 2 vetores Qdrant, 1 entrada em manifesto. `validate_incremental_bundle` validou as identidades cruzadas entre SQLite, manifesto e Qdrant. Os tr?s hashes SHA256 do RAG publico (manifesto, SQLite, Qdrant) permaneceram IDENTICOS ao baseline 2026-10-20 apos a operacao.

**Limites:** bundle aprovado e de apenas uma fonte (delta), NAO e a geracao combinada de 211 documentos e nao esta pronto para promocao; nenhuma copia do Qdrant publico aberto foi tentada. O staging em pasta TEMP sera preservado apenas como evidencia temporaria, sujeito a limpeza do Windows. Geracao/publicacao de producao seguem `GO-LIVE BLOCKED`. Scheduler e worker automaticos permanecem desativados.

Proxima etapa P2 exige baseline fechado comprovado e merge sem copiar armazenamento publico aberto, seguido de provas integrais de identidades e freshness. A autorizacao atual nao permite indexar outras fontes nem publicar.
