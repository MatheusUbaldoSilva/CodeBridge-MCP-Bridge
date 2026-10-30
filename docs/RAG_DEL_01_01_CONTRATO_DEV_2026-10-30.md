# RAG-DEL-01.01 — Contrato de exclusão de conhecimentos (DEV)
Data: 2026-10-30
Estado: AUDITORIA E CONTRATO DOCUMENTADOS; nenhuma exclusão executada
Branch: dev-local. Escopo: apenas índices privados e isolados.

## Mapeamento fundamentado no código
- rag/runtime/isolated_project_index.py: catálogo por projeto, validação do recibo de geração e SHA-256 do SQLite/manifesto, resolução fail-closed.
- rag/runtime/auto_index_generation.py: validação independente de job, origem, SQLite/FTS, manifesto e Qdrant; geração verificada e snapshot.
- rag/runtime/auto_index_canary.py: ativação com backup, journal, lock e escrita atômica; rollback por job. A ativação atual recusa projetos previamente registrados: **reposição de geração ainda não implementada**.
- rag/index/purge.py: exclusão derivada por projeto inteiro; NÃO reutilizar para exclusão individual na geração ativa.
- rag/runtime/auto_index_incremental_{manifest,sqlite,transfer,verify}.py: provas de elegibilidade e cópia em lotes de vetores preservados, exclusivamente em staging.
- app_rewrite/rag_panel.py: listagem de arquivos por projeto; interface de exclusão ainda não implementada.

## Contrato obrigatório da futura operação
1. Só projeto privado isolado, nunca namespace codebridge nem ponteiro público.
2. Prévia somente leitura: caminhos exatos, SHA-256, total de documentos/chunks/vetores a excluir, conjunto preservado, geração ativa e revisão. Sem seleção por padrão.
3. Consentimento explícito vinculado a projeto, geração, revisão e hash da seleção; um pedido por job.
4. Criação de nova geração imutável (não editar SQLite, FTS, Qdrant, manifesto, progress ou recibos da geração anterior).
5. Reutilizar vetores preservados somente após conferir modelo, dimensões, namespace, chunks, payload e readback. Se não houver vetor seguro, falhar fechado; não apagar original.
6. Recalcular em staging os documentos/chunks/FTS/manifesto e contagens; validar SHA-256 e recibos antes de qualquer ativação.
7. Implementar transição atômica versionada para substituir a entrada privada de um projeto já registrado, com lock, journal, backup e rollback verificável. Não chamar activate_auto_canary como se já suportasse substituição.
8. Preservar a geração anterior e arquivo-fonte original. Exclusão significa retirar o conhecimento da nova geração lida pelo projeto; não apagar backups automaticamente.
9. Recusar remoção com worker/reserva ativa, alteração de catálogo, seleção stale, symlink/junction, mudança de revisão, geração em uso sem proteção ou inconsistência.
10. Suportar exclusão individual, múltipla e de todos os conhecimentos com confirmação reforçada para projeto inteiro. Operação total NÃO é equivalente a deletar arquivos de origem.
11. Comprovar isolamento entre projetos e proteção da Stable e índice público. Fazer testes de falha antes/depois do switch, reabertura e rollback.
12. Sem push, publicação na Stable, nem operação destrutiva até autorização e auditoria específica.

## Fases seguintes (dividir para conquistar)
- RAG-DEL-01.02: prévia/seleção segura com testes negativos; somente leitura.
- RAG-DEL-01.03-A: construção de candidato SQLite+FTS/manifesto.
- RAG-DEL-01.03-B: cópia validada de vetores sobreviventes Qdrant.
- RAG-DEL-01.03-C: geração imutável, recibos e integridade.
- RAG-DEL-01.04-A: transição versionada de catálogo com lock e journal.
- RAG-DEL-01.04-B: rollback/falhas injetadas, isolamento de projeto e recuperação.
- RAG-DEL-01.05: interface de seleção, confirmação e homologação DEV; patch notes e Git auditado.

## Critérios de fechamento da fase 01.01
- Mapeamento de APIs, bloqueio de substituição de projeto identificado.
- Riscos e invariantes escritos; nenhuma alteração em dados reais.
- Revisão documental e teste simples de contrato (fases seguintes terão testes executáveis).
- Commit local somente após diff/escopo revisados, preservando pendências preexistentes.
