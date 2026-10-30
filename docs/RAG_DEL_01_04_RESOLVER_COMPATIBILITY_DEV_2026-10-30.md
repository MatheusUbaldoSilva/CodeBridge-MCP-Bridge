# RAG-DEL-01.04 — Contrato de compatibilidade com resolver de gerações
Data: 2026-10-30
Estado: auditoria; nenhuma ativação operacional.

## Bloqueio crítico
O resolver `rag/runtime/isolated_project_index.py` aceita `index_family=RAG_AUTO_03` com job_id, nomes de geração e snapshot, auto-generation-receipt.json, progress.json e hashes; fora desta família aplica contrato legado source_revision de 40 caracteres e progress PASS. O staging RAG-DEL atual oferece recibo de evidência e bundle de revisão, **não** uma geração completa registrada e reconhecida pelo resolver.

Não é seguro usar a linha RAG_AUTO_03 para uma exclusão: o recibo do job e as contagens são de outra geração. Também não se deve simular o legado para contornar a verificação.

## Próximo desenvolvimento obrigatório
1. Definir família explícita RAG_DEL_01 em contrato de leitura, com recibo próprio imutável e completo.
2. Vincular geração-base, seleção aprovada, snapshot-fonte, chunks remanescentes, SQLite/FTS/manifesto, Qdrant e checkpoints numa prova verificável.
3. Validar caminho dentro do workspace, SHA-256 dos artefatos e inviolabilidade do índice ativo; fail-closed para dados incompletos.
4. Testar sem registrar no catálogo real: candidato válido, recibo adulterado, progress divergente, namespace incorreto, rollback antigo e preservação de outros projetos.
5. Somente após isso ligar a transição catalogada e confirmada com rollback sob lock/fencing.

## Evidências de hoje
- Preview real de newworldpvp: 435 arquivos, seleção de 1 -> 27 chunks; seleção de 2 -> 84 chunks, 433 preservados, hash determinístico, nenhuma remoção.
- UI de seleção e revisão somente leitura montada no DEV; commits dc5bfb7, a2a0943, ad0fb98, 172ea29.
- Revisão combinada SQLite/manifesto/Qdrant fechada, commit bfedb82.
- Regressão conjunta registrada: 336 testes, 329 aprovados, 7 dispensados, 0 falhas (antes dos 5 testes do bundle).

Stable, índice público e geração privada real não foram modificados.
