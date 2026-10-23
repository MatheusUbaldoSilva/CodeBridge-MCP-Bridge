# P9-B ? Prova independente pelo Agendador do Windows

Data: 2026-10-23
Escopo: laborat?rio controlado e produ??o somente leitura.

## Evid?ncias reais

1. O Agendador do Windows iniciou Python fora da ?rvore de processos da instala??o ativa. Ancestralidade: EXTERNAL_PROCESS_ANCESTRY_VERIFIED.
2. O processo independente executou o teste test_rag_p9b_detached_combined_hardcrash_chain_e2e.py em diret?rio tempor?rio, envolvendo arquivos, atalhos e HKCU simulado, com queda abrupta e retomada por segundo processo: 1 teste, 0 falhas, 0 erros.
3. O script versionado installer/p9b_scheduled_combined_lab.ps1 reproduziu a prova: SCHEDULED_COMBINED_LAB_VERIFIED; cleanup sem tarefa ou pasta tempor?ria.
4. Outra tarefa independente executou recover_detached_combined(production=True) contra a instala??o ativa, com identidade real do staging ee337ec8ee8ecff5fd987e8d597a4b691a02b35c e workers espias inofensivos. Resultado: DETACHED_COMBINED_RECOVERY_REFUSED, motivo INDEPENDENT_POSTSTOP_REQUIRED, workers_invoked=[], authorized=false.
5. Ambas as tarefas foram desregistradas e seus diret?rios tempor?rios removidos.

## Limita??es

A prova de muta??o e replay ocorreu SOMENTE em TemporaryDirectory com HKCU simulado. Na instala??o ativa, provou-se apenas a recusa sem altera??es. Nenhum NSIS real foi executado, GUI/MCP n?o foram encerrados, e nenhuma fila RAG foi tocada. N?o certifica HKCU real, queda total de energia, rein?cio autom?tico ou CBMCP/1.

P9-B ABERTO. Pr?ximos gates: supervisor transacional persistente externo, HKCU real em escopo controlado, rollback integral apos crash, p?s-update MCP/RAG, auditoria Git e autoriza??o antes do NSIS.
