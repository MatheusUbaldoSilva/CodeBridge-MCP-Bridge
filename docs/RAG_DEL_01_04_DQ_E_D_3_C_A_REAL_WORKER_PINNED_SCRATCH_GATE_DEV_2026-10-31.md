# RAG-DEL-01.04-DQ-E-D-3C-A — Real worker entrypoint, scratch pin-only (DEV)

## Entrega

Em rag/runtime/isolated_project_worker.py foi adicionada uma rota opt-in de CLI --pinned-scratch-only <TEMP root> que recebe uma PinnedSemanticRequestV1 via stdin limitado a 8192 bytes, valida a identidade do envelope, projeto/revisao/geracao e SHA256 de catalogo, SQLite e manifesto exclusivamente em TemporaryDirectory direto e retorna LAB_SEMANTIC_REQUEST_VALIDATED. Nao chama resolve_isolated_project, search_persistent_semantic, Qdrant ou modelos neste caminho. Flags inesperadas sao recusadas. A entrada legada sem flags permanece inalterada.

O pai de laboratorio reutiliza execute_semantic_roundtrip_lab com um runner de teste que executa o modulo real isolado no novo modo. Verifica resposta e nonce/digest. Nenhum caminho de producao utiliza esse runner.

## Testes e evidencias

7 testes novos PASS:
- Roundtrip com processo real e nonce, geracao, digest e flags nao-operacionais.
- O novo ramo nunca chama resolucao do indice registrado ou busca semantica (mocks fail-on-call).
- Entrada legada recebe projeto e efetua busca sintetica sem quebra de contrato.
- CLI invalida e raiz fora do TEMP falham fechados.
- Mutacao do catalogo entre pin do pai e leitura do filho e recusada.
- Lock de geracao exclusivo de outro processo e bloqueado enquanto a sessao do pai esta viva; liberado depois da sessao.

RAG-DEL 393 testes executados, 389 PASS, 4 SKIP, zero falhas.
RAG-AUTO sem MCP 241 testes executados, 236 PASS, 5 SKIP, zero falhas.
Total 634 executados, 625 PASS, 9 SKIP e 0 falhas.

## Limites e proximo passo

Este modo confirma o protocolo pinado no codigo do entrypoint real, NAO inicia a inferencia semantica real nem prova o processo instalado. Faltam binding para index workspace aprovado, liveness do pai durante modelos, verificacao da geracao apos a busca e atestacao de lock/cancelamento, mantendo o legado intacto. DQ-E-D-3C-B deve exercitar verificacao de destino de indice e caminho de dados aprovados com modelos simulados, sem promover a feature para MCP conectado, Stable ou producao.

Nao houve alteracao de indice/catologo real, fila, GUI instalada, Stable, GitHub ou autorizacao de exclusao.