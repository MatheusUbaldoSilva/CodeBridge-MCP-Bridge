# RAG-017 — Pós-validação de escopo da fusão experimental

Introduzido `rag/runtime/experimental_scope_guard.py`, executado **apenas** após a fusão `experimental_cross_route` em `search_persistent_semantic`. O guard valida os metadados finais contra a consulta: `project_id`, branch, `source_types` e fragmento normalizado de `path_filter`. Resultados divergentes são rejeitados por exceção, em vez de expostos ao solicitante.

Seis testes exercitam resultado válido, projeto indevido, branch indevida, fonte indevida, caminho fora de escopo e ausência de caminho. A regressão RAG passou com **798 testes**. Não houve alteração dos parâmetros padrão, indexação ou modelos. Observação: a verificação de escopo pós-fusão é uma defesa adicional, não comprova sozinha a segurança de autorização/autenticação de ponta a ponta nem a integridade de metadados armazenados. O gate de produção segue BLOCKED e a build dual candidata permanece preservada.
