# Patch notes — RAG-AUTO-05 / DEV
2026-10-26

## Alteracoes
- Planejamento incremental por SHA-256, proveniencia de fontes e revisoes de modelos.
- Reuso verificado de vetores Qdrant Local em staging isolado; lote TEXT/CODE maximo de 256 pontos.
- Confirmação de aprovacao do job, lock semantico, lease fencing e heartbeat.
- Checkpoints duraveis e readback Qdrant; identificacao de falhas e quarentena nao destrutiva.
- Runner supervisionado com batch_index, checkpoint oficial QUEUED/READY_FOR_REVIEW e verificacao de geracao publica.
- Testes unitarios e integracao com jobs/SQLite/Qdrant reais em diretorios temporarios.

## Validacao e ressalva
- Regressao RAG/Qt: 241 testes, 236 PASS, 5 SKIP, 0 FAIL.
- MCP: 5 testes PASS; testes RAG-AUTO-05: 112, 109 PASS, 3 SKIP.
- Jina CODE real e transferencia para staging isolado: PASS.
- Jina TEXT CPU real: NAO EXECUTADO, validacao adiada por decisao expressa do usuario.
- Falhas eventualmente observadas na validacao posterior exigem patch e nova auditoria.

## Alcance
Commit exclusivo na branch dev-local. Nenhuma publicacao GitHub, implantacao Stable ou ativacao de indice publico. Tres pendencias antigas excluidas.
