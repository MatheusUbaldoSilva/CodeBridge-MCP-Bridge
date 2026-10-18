# RAG-LAB.04 — Atualização de restauração sintética

Data: 2026-10-18

## Evidências incrementais

- d18a7d0: rechecagem de sidecars internos Qdrant e SQLite principal tanto no snapshot quanto no staging imediatamente antes da publicação da restauração.
- f72cecc: WAL, SHM e journal do SQLite principal tardios no snapshot.
- 6f53226: WAL, SHM e journal de Qdrant tardios no staging.
- fb0f552: WAL, SHM e journal do SQLite principal tardios no staging.
- f4adf27: documentação do mecanismo, limitação TOCTOU residual e proibição de uso em produção.
- 498372a: alteração no conteúdo do snapshot de origem após validação da cópia, antes de publicação, foi reproduzida e bloqueada com comparação final de hashes.

Última regressão integrada: 390 PASS = 262 offline + 83 generation + 7 preflight + 38 incremental. Commits isolados e publicados com HEAD igual ao upstream.

## Limites

Esses testes usam apenas a fixture descartável codebridge-rag-generation-test. Uma checagem imediatamente antes do rename não equivale a lock transacional contra escritores externos durante o próprio rename. Não há evidência global de todos os processos Windows, handles, mappings, indexadores e leitores reais, nem autorização específica de manutenção.

RAG-LAB.04 normativo: PARCIAL.
RAG-LAB.05 operação de produção: NÃO AUTORIZADA.

copy_authorized=false
all_handles_closed=false
production_quiescence_proven=false
production_backup=BLOCKED
