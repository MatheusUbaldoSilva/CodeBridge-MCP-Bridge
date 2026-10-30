# RAG-DEL-01.03-C — Verificação estrutural candidata (DEV)
Data: 2026-10-30
Estado: VERIFICADOR SOMENTE LEITURA IMPLEMENTADO EM LABORATÓRIO.

## Construído
- `rag/runtime/knowledge_deletion_verify.py`: confere integridade SQLite, caminhos e SHA-256 dos documentos contra manifesto sobrevivente, contagem e identidade de chunks, contagem FTS, ausência de outro namespace e inventário de vetores.
- Para cada lote exige recibo durável e relê os vetores via validador original do RAG-AUTO-05, conferindo namespace, dimensões, SHA, IDs e quantidade.
- Retorna `DELETION_STAGING_STRUCTURALLY_VALID` com `generation_receipt_created=False` e `activation_authorized=False`.
- `tests/test_rag_del_01_03_c_verify.py`: verificação em SQLite e recibos temporários; teste positivo e recusa de desvio de hash, ausência de recibo, total incorreto e projeto público.

## O que ainda falta
- Validação end-to-end usando todo o Qdrant temporário para vários lotes, injeção de falhas e verificação de dimensão/payload, sem modelos.
- Guardar uma geração imutável com recibo de proveniência de ponta a ponta e política de fontes excluídas.
- Criar a rotina versionada de substituição de catálogo com lock, snapshot e rollback (RAG-DEL-01.04).
- Homologar sem tocar no `newworldpvp` nem publicar no índice público.

Não executar estágio na origem real nem tratar este resultado como autorização de ativação.
