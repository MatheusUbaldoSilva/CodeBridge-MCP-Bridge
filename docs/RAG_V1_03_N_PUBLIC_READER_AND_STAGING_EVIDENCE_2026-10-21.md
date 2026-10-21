# RAG V1.03-N ? Evidencias do leitor publico e geracao isolada

Data 2026-10-21 | base cca03ed | auditoria de leitura e fixture

## Evidencias observadas no processo MCP instalado

`author_mcp/v1_public_readiness.py` via Python do MCP, contra `http://127.0.0.1:8765/mcp`, retornou `READY_FOR_CONCURRENT_READONLY_TEST` com PID MCP 5936, geracao `legacy`, leitores protegidos, serializacao do worker semantico e `OBSERVED_CONSISTENT` cruzando SQLite, manifesto e Qdrant (210 documentos e 8761 chunks). A execucao com `--concurrent` retornou `PUBLIC_HYBRID_CONCURRENCY_PASS` com tres consultas HYBRID, cada uma com 3 resultados e sem fallback nem erro. `safe_to_activate=false` e `index_pointer_updated=false` permanecem.

## Evidencias isoladas

`python -m unittest discover -s tests -p test_generation_incremental_live_publish.py -q` => 2 PASS.
`python -m unittest discover -s tests -p test_incremental_offline_publish.py -q` => 3 PASS.

Sao fixtures/test roots e nao um corte de geracao publica.

## Pendencias precisas

- Vincular geracao candidata fechada, staging de vetores e SQLite a revisao aprovada e verificacao de todas as identidades de chunks.
- Provar publicador versionado completo sob lock exclusivo com journal e recuperacao em falhas em runtime autorizado sem perder consultas protegidas.
- Testar fim-a-fim o novo indice de codigo com a mesma proveniencia e verificacao Git sem alterar a geracao legacy ate haver autorizacao.
- Obter autorizacao individual de fonte e autorizacao especifica da transicao; nao equiparar prova de leitura a GO-LIVE.

**Decisao:** RAG publico intacto, indexacao incremental ainda `GO-LIVE BLOCKED`. Nao remover os motivos de bloqueio do preflight apenas com base nas provas de leitura.
