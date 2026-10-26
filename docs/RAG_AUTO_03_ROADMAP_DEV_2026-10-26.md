# RAG-AUTO-03 — Gerações verificadas, canário e reversão (DEV)

Data: 2026-10-26
Base: commit RAG-AUTO-02 6db33d5c9a878591e665391570a1ed168092aa18
Estado: IMPLEMENTADO E VALIDADO NO DEV (canário isolado) — NÃO FAZER CUTOVER PÚBLICO
Git: dev-local, sem push por subfase

## Limite de segurança

A geração pública CodeBridge `active-generation.json` NÃO será alterada neste marco sem um pedido explícito e separado para cutover. O projeto de indexação automática utiliza catálogo multiprojeto isolado e independente. Qualquer implantação real no catálogo existente requer consentimento específico e auditoria prévia das gerações já registradas.

## Subfases (6)

- **03.1** Auditar publicação legada, fixar contrato de geração e limites de segurança.
- **03.2** Validar todo job READY_FOR_REVIEW: SQLite, FTS5, manifesto, hashes das fontes, Qdrant, revisão e contadores.
- **03.3** Copiar staging e fontes para snapshot imutável sob workspace, validar novamente os hashes e criar recibo versionado; sem registro público.
- **03.4** Habilitação controlada no catálogo multiprojeto, registro atômico e backup anterior; sem troca do ponteiro global.
- **03.5** Desabilitar/reverter registro e testar interrupções, sem apagar versões; preservar estado anterior mesmo quando o índice novo não estiver disponível.
- **03.6** Bateria com testes temporários, consulta real MCP isolada, prova de não alteração da geração pública; auditoria diff/commit pós-fase.

## Referências existentes

- `generation_activation.py`, `generation_verified_backup.py`, `generation_journaled_publish.py` são principalmente test-only e não devem ser usados diretamente para mudar produção.
- `production_generation_transition.py` trata migração específica do legado e não é mecanismo genérico de substituição.
- `isolated_project_index.py` já sabe consultar registros isolados, mas o contrato antigo espera Git commit SHA de 40 caracteres e progress.last_batch_result PASS. O job automático usa source_review SHA-256 de 64 caracteres e COMPLETE. Estender por tipo de registro, preservando o comportamento antigo.
- O job automático anterior é produzido por `auto_index_worker.py`; estágio permanece `published=false` até ativação de leitura específica. Fonte original será congelada em snapshot copiando apenas arquivos aprovados.

## Política de Git

Não commitar durante subfases; quando o escopo estiver funcional: testar, auditar diff, commitar no dev-local, auditar pós-commit. Nenhum push enquanto RAG-AUTO-COMPLETE não estiver funcional e houver autorização do usuário.
