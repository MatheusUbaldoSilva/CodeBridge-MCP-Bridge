# RAG-DEL-01.04-A — Executor transacional em laboratorio (DEV)
Data: 2026-10-30
Estado: **LABORATÓRIO APENAS**; NÃO autoriza exclusão real.

- `knowledge_deletion_swap_lab.py`: troca compare-and-swap do catálogo temporário com lock reutilizado do RAG-AUTO, backup exato, journal PREPARED, atualização atômica, conferência do ponteiro público e rollback compare-before-restore.
- `test_rag_del_01_04_a_swap_lab.py`: valida a troca, isolamento de outros projetos, rollback idempotente, falhas injetadas antes/depois da substituição, catálogo alterado, backup alterado, ponteiro público alterado, revisão obsoleta, ausência de aprovação e rejeição de diretórios fora do laboratório.
- Bloqueio proposital: o executor só aceita arquivos temporários em diretórios scratch nomeados tmp* e `laboratory_mode=True`. Não há vínculo de ativação com catálogo real nem UI.

## Critérios pendentes para executor operacional
- Recibo completo de geração imutável compatível com o resolver e recibo dos vetores, não apenas a evidência estrutural atual.
- Proveniência end-to-end e defesa contra path redirection/junction TOCTOU.
- Revalidação do estado canary ativo, journals existentes e workers concorrentes.
- Testes de crash/restart, rollback de múltiplas gerações e confirmação explícita.
- Nenhum uso com `newworldpvp` ou com Stable até homologação.
