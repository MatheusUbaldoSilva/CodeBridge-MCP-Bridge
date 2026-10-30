RAG-DEL-01 — Patch notes DEV, continuidade 2026-10-30

Entregas: a531903 planejamento de recuperacao somente leitura; 2eb9a32 integridade SHA256 de journal; 5768ac0 concorrencia multiprocessos e rollback em outro processo; 35c6d77 preflight de catalogo privado; 95d1f8c verificacao de backup; 7e2ad96 contrato de revisao; cd8d110 hashes imutaveis; 3873887 invalidacao de confirmacao obsoleta; e63c617 snapshot de fontes; 2bfbb37 prova de snapshot obrigatoria na revisao; 47deb7c tamanho do arquivo; 4c94d03 prova de snapshot obrigatoria no gate de transicao.

Validacoes: RAG-DEL 189 testes (187 PASS, 2 SKIP); RAG-AUTO 241 testes (236 PASS, 5 SKIP); MCP 5 PASS. Total 435, zero falhas nas suites separadas. Snapshot real newworldpvp verificado somente leitura: 435 arquivos, 4.358.269 bytes, hash e tamanho compativeis.

Continuam bloqueadas: exclusao real, troca operacional do catalogo e ativacao da geracao. Faltam fencing de workers em producao, verificacao final do candidato fechado sob lock, rollback e homologacao de falhas. Sem alteracao na Stable, no indice publico ou nas fontes reais; sem push.

RAG-DEL-01.04-J (DEV): journals terminais ROLLED_BACK passam a exigir identidade, schema, backup existente e SHA-256 consistente antes de autorizar nova transacao de laboratorio. Novos testes em tests/test_rag_del_01_04_j_terminal_journal.py: 7 PASS. Suite RAG-DEL no runtime dev: 196 executados (194 PASS, 2 SKIP), zero falhas. Nao habilita exclusao real nem ativacao operacional; sem push.

RAG-DEL-01.04-K (DEV): segunda validacao do recibo da geracao candidata enquanto o mutex do catalogo estiver adquirido, imediatamente antes de qualquer backup/journal. Se a geracao se tornar invalida entre as duas verificacoes, troca e journal sao abortados no laboratorio. Testes RAG-DEL: 199 (197 PASS, 2 SKIP). RAG-AUTO, sem o caso MCP que exige runtime separado: 241 (236 PASS, 5 SKIP). Sem ativacao operacional.

RAG-DEL-01.04-L (DEV): reauditoria de proveniencia da candidata dentro da secao critica de catalogo no laboratorio, comparando linhagem, snapshot, manifesto, contagem de sobreviventes e flags de nao ativacao. Alteracao de prova bloqueia a transacao. RAG-DEL: 201 testes (199 PASS, 2 SKIP), sem falhas. Sem worker fencing operacional, sem exclusao real ou push.
