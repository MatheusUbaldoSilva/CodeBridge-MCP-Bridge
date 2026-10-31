# RAG-DEL-01.04-DQ-E-D-3A — Requisicao semantica IPC sob pin sintetico

## Escopo concluido
- Novo PinnedSemanticRequestV1 imutavel em knowledge_deletion_semantic_request_lab.py, com envelope DQ-E-D-1, query, route, top_k, source_types, path_filter, branch e sha256 canonico da requisicao (identidade somente, NAO autenticacao).
- Worker exclusivamente de LAB knowledge_deletion_pin_worker_lab.py suporta --semantic-request: valida formato estrito, namespace, rota TEXT/CODE/HYBRID (nunca LEXICAL_ONLY), top_k 1-20, tamanho e tipos de filtros, proibe path absolutos/caminho pai e campos extras. Em seguida confere catalogo, geracao, revisao e hashes SQLite/manifesto em TEMP e retorna resultado sem inferencia.
- Integracao com dispatch_semantic_already_locked_lab: chamada entre pai/filho ocorre enquanto a sessao semantica de laboratorio retém os locks, sem readquirir semantic.

## Provas
6 testes DQ-E-D-3A PASS. Real child recebe nonce, generation_id e request_sha256 esperados. Rejeita rotas, queries, filtros e top_k malformados; bloqueia paths injetados e mudanca de catalogo; query nova altera digest; protocolo nao habilita modelo nem operacao real.
RAG-DEL 379 testes (375 PASS, 4 SKIP); RAG-AUTO non-MCP 241 testes (236 PASS, 5 SKIP), total 620 (611 PASS, 9 SKIP), zero falhas.

## Limites
Este worker de laboratorio NAO e isolated_project_worker.py real. Nao usa Qdrant nem modelos, nao atesta locks no filho, e o sha256 de request NAO e assinatura de autenticidade. A prova de seguranca vem da retencao externa dos locks sob a sessao privada de laboratorio e da validacao dos artefatos.

Proximo DQ-E-D-3B: contrato de handoff no worker real em DEV com teste de compatibilidade legado e rota pinada fail-closed; antes de habilitar caminho semantico real, adicionar atestacao efetiva da geracao e garantias de vida/lock do pai. Sem integracao operacional ou ativacao de exclusao.