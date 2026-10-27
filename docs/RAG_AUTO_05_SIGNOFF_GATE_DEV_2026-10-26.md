# RAG-AUTO-05 — Gate de fechamento (DEV)
Data: 2026-10-26
Branch autorizada: `dev-local` · base `05d0147`
Status: **FECHAMENTO LOCAL AUTORIZADO COM RESSALVA TEXT CPU**

## Evidências verificadas
- Reutilização incremental em Qdrant Local isolado; divisão determinística em lotes de até 256.
- Jina CODE real: inferência realizada somente na origem, reutilização sem nova inferência no destino.
- Teste ponta a ponta TEXT+CODE com dois lotes de um vetor: QUEUED depois do primeiro e READY_FOR_REVIEW depois do segundo.
- Rejeição de batch_index inválido; reuso apenas para fontes com hash, aprovação e modelo compatíveis.
- Supervisor com fencing, heartbeat, lock semântico, checkpoint durável e rollback por quarentena não destrutiva.
- Proteção contra corrida de lease e mudança de estado de job dentro do lock.
- Regressão final: 241 testes RAG/Qt, 236 PASS, 5 SKIP, 0 FAIL.
- Testes MCP separados: 5 PASS; Qt nativo Windows: 17 PASS; testes repetidos multi-lote e crash: 15 PASS.

## Validacao TEXT CPU adiada por decisao expressa do usuario
- **Jina TEXT CPU real**: teste opt-in recusou carregamento por RAM < 3000 MiB (última medição: 2786 MiB).
- Inspeção final dos arquivos alterados e diff completo, revisão de segurança, commit exclusivamente local e auditoria pós-commit.
- Não integrar à Stable, não promover geração pública, não fazer push sem autorização expressa.

## Exclusões obrigatórias na auditoria Git
- `benchmarks/rag017_code_only_extended_smoke.json`
- `docs/RAG_017_J_VM_ROLLBACK_RUNBOOK_2026-10-10.md`
- `rag/runtime/incremental_installed_queue_init.py`

## Política
A politica de fechamento exige auditoria do diff, commit local e verificacao pos-commit. O canario TEXT CPU nao esta aprovado e permanece como risco residual pos-fechamento.

## Decisao de homologacao posterior (autorizada pelo usuario)
O canario Jina TEXT CPU foi explicitamente adiado para validacao posterior. Nao considerar PASS; preservar SKIP e registrar risco residual de erro de inferencia/reutilizacao TEXT real. Defeitos futuros serao corrigidos em patch separado com testes. Esta dispensa especifica nao substitui as demais auditorias de fechamento.
Nenhuma publicacao, alteracao na Stable ou no indice publico foi autorizada.
