# RAG-DEL-01.04-DM — Inventário privado com mutex de catálogo em laboratório

## Lacuna de leitura privada

O resolvedor isolated_project_index.resolve_isolated_project() já verifica fingerprint de SQLite/manifesto e a estrutura de geração. Mas search_isolated_project, get_isolated_project_context e a rota GUI privada ainda não mantêm uma trava cooperativa de catálogo durante toda a leitura. A troca de geração de laboratório usa o mutex auto-canary.lock, portanto uma consulta não pinada pode perder a relação com a geração depois da validação inicial.

## Implementação não operacional

O módulo knowledge_deletion_private_inventory_lab.py contém laboratory_private_inventory_locked. O mecanismo:
- exige laboratory_mode=True e operator_approved=True;
- reusa a validação scratch-only de _lab_paths e aceita somente catalogo project-indexes.json sob TemporaryDirectory;
- rejeita índice público codebridge, geração redirecionada, SQLite inexistente e journal de exclusão pendente;
- mantém o mesmo _catalog_mutex utilizado pelo laboratório de swap durante leitura SQLite mode=ro/query_only;
- compara o hash SHA256 do SQLite com o fingerprint registrado e revalida catálogo e índice após a consulta;
- retorna LAB_PRIVATE_INVENTORY_READ_ONLY e activation_authorized=False, operational_use_allowed=False.

O mutex cria seu arquivo auto-canary.lock exclusivamente no diretório TEMP autorizado. Não escreve nem consulta índices privados instalados.

## Testes

Sete testes em bancos temporários exercitam inventário por namespace, fidelidade de hashes, fonte pública sentinela excluída, journal pendente, rejeição sem aprovação e concorrência real de outro processo mantendo o mutex.

A cooperação do laboratório mostra uma possível estratégia, mas NÃO certifica o protocolo global de leitores privados: a produção exige provar que todos os caminhos GUI/MCP/legados mantêm a mesma trava, que a trava cobre cada operação SQLite e Qdrant, e que existe ordenação segura frente a generation/semantic/queue.

## Próximo trabalho

Certificar uma sessão de leitura privada multi-processo pinada, políticas de timeout/erro em GUI, threads semânticas, isolamento do catálogo e rollback; integrar somente após homologação. Excluir conhecimento operacional permanece desabilitado, sem push e sem modificação Stable.