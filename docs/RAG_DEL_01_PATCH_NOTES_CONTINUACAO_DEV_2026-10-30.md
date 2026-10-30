RAG-DEL-01 — Patch notes DEV, continuidade 2026-10-30

Entregas: a531903 planejamento de recuperacao somente leitura; 2eb9a32 integridade SHA256 de journal; 5768ac0 concorrencia multiprocessos e rollback em outro processo; 35c6d77 preflight de catalogo privado; 95d1f8c verificacao de backup; 7e2ad96 contrato de revisao; cd8d110 hashes imutaveis; 3873887 invalidacao de confirmacao obsoleta; e63c617 snapshot de fontes; 2bfbb37 prova de snapshot obrigatoria na revisao; 47deb7c tamanho do arquivo; 4c94d03 prova de snapshot obrigatoria no gate de transicao.

Validacoes: RAG-DEL 189 testes (187 PASS, 2 SKIP); RAG-AUTO 241 testes (236 PASS, 5 SKIP); MCP 5 PASS. Total 435, zero falhas nas suites separadas. Snapshot real newworldpvp verificado somente leitura: 435 arquivos, 4.358.269 bytes, hash e tamanho compativeis.

Continuam bloqueadas: exclusao real, troca operacional do catalogo e ativacao da geracao. Faltam fencing de workers em producao, verificacao final do candidato fechado sob lock, rollback e homologacao de falhas. Sem alteracao na Stable, no indice publico ou nas fontes reais; sem push.

RAG-DEL-01.04-J (DEV): journals terminais ROLLED_BACK passam a exigir identidade, schema, backup existente e SHA-256 consistente antes de autorizar nova transacao de laboratorio. Novos testes em tests/test_rag_del_01_04_j_terminal_journal.py: 7 PASS. Suite RAG-DEL no runtime dev: 196 executados (194 PASS, 2 SKIP), zero falhas. Nao habilita exclusao real nem ativacao operacional; sem push.

RAG-DEL-01.04-K (DEV): segunda validacao do recibo da geracao candidata enquanto o mutex do catalogo estiver adquirido, imediatamente antes de qualquer backup/journal. Se a geracao se tornar invalida entre as duas verificacoes, troca e journal sao abortados no laboratorio. Testes RAG-DEL: 199 (197 PASS, 2 SKIP). RAG-AUTO, sem o caso MCP que exige runtime separado: 241 (236 PASS, 5 SKIP). Sem ativacao operacional.

RAG-DEL-01.04-L (DEV): reauditoria de proveniencia da candidata dentro da secao critica de catalogo no laboratorio, comparando linhagem, snapshot, manifesto, contagem de sobreviventes e flags de nao ativacao. Alteracao de prova bloqueia a transacao. RAG-DEL: 201 testes (199 PASS, 2 SKIP), sem falhas. Sem worker fencing operacional, sem exclusao real ou push.

RAG-DEL-01.04-M (DEV): testes ponta a ponta em catalogo temporario validam integracao da reauditoria sob mutex: divergencia de manifesto causa abort sem gravar journal/backup, e provas estaveis permitem troca e rollback mantendo projeto vizinho e ponteiro publico. Suite RAG-DEL: 203 testes (201 PASS, 2 SKIP). Teste real com workers ainda pendente; ativacao permanece bloqueada.

RAG-DEL-01.04-N (DEV): detecta backups orfaos rag-del-*.previous.json sem journal correspondente no preflight e antes da troca do catalogo temporario; falha de fechamento seguro sem gravar novo journal. Testes: 3 novos aprovados, RAG-DEL 206 executados (204 PASS, 2 SKIP), zero falhas. Nenhum catalogo real alterado.

RAG-DEL-01.04-O (auditoria DEV, sem codigo operacional): o mecanismo production_generation_lock possui canais independentes generation e semantic. production_generation_transition protege o cutover com generation exclusivo, enquanto auto_index_incremental_fenced utiliza semantic exclusivo e lease do supervisor. Logo, um lock generation isolado NAO prova quiescencia de todos os escritores semanticos. Antes da exclusao real e necessario definir ordem de aquisicao de ambos os canais, evitar deadlock, drenar workers, verificar leases, bloquear novos jobs e testar rollback operacional em isolamento. A troca real permanece proibida.

RAG-DEL-01.04-P/Q/R (DEV): barreira SQLite BEGIN IMMEDIATE em fila temporaria do supervisor, locks injetados ordenados fila -> generation -> semantic, rejeicao de leases (inclusive expiradas) e jobs pendentes, prova de concorrencia multiprocessos, swap/rollback isolado e simulacoes de crash real (os._exit) com reconciliacao explicita. Testes RAG-DEL 222 (220 PASS, 2 SKIP), zero falhas. Nao autoriza nenhuma ativacao real.

RAG-DEL-01.04-S (DEV): 2 testes com LockFileEx efetivo do CodeBridge, ambos canais sob root sintetico mockado, cobrindo exclusao de outro processo e desalocacao parcial ao falhar no segundo lock. Somente scratch, nao altera root de producao nem libera exclusao real.

RAG-DEL-01.04-T (DEV): revisao somente leitura do supervisor AUTO em SQLite existente (mode=ro, query_only), sem criar banco ou alterar leases. Detecta fila ausente, schema invalido, integridade, lease ativa ou expirada, e jobs nao terminais. Resultado observado quieto continua activation_authorized=False e queue_barrier_held=False. Testes: 11 novos PASS; RAG-DEL 235 testes (233 PASS, 2 SKIP); RAG-AUTO 241 testes (236 PASS, 5 SKIP), sem falhas em suites executadas.

RAG-DEL-01.04-U/V (DEV): adaptador de transicao provenance-gated de laboratorio exige barreira da fila + dois locks antes de chamar swap; revisao previa READ_ONLY do supervisor agora carrega hash da identidade do caminho, e o adaptador confere flags imutaveis e a geracao singleton dentro da barreira. Mudanca de geracao entre revisao e swap exige revisar novamente. 12 testes de adapter aprovados; suite RAG-DEL 247 (245 PASS, 2 SKIP), 0 falhas. Ativacao e exclusao operacionais continuam negadas; nao ha promocao remota.

RAG-DEL-01.04-W (DEV): regressao valida que READY_FOR_REVIEW, apesar de nao manter lease ativo, continua bloqueado por nao ser estado terminal resolvido de fila. Auditoria real somente leitura confirma necessidade de reconciliar/revisar estados antes de homologacao, sem revelar job IDs nem alterar fila. Nenhuma operacao mutavel foi realizada.
