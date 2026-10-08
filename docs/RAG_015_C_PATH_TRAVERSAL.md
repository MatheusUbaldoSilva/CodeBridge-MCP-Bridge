# RAG-015-C — Path traversal

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-015-security`

## Objetivo

Impedir que qualquer operação RAG alcance arquivos fora das raízes autorizadas

Requisito do handoff

`Bloquear caminhos fora das raízes autorizadas`

## Vetores testados

Foram usados caminhos adversariais em formatos POSIX Windows e absoluto

Exemplos

```text
../outside.py
docs/../../outside.md
..\outside.py
docs\..\..\outside.md
C:\...\outside.py
```

## Denylist

`classify_denied_path()`

normaliza separadores Windows para POSIX e classifica qualquer segmento `..` como

`PATH_TRAVERSAL`

A prova cobre os dois formatos de separador

## Planejamento de indexação

`plan_rag_index()`

resolve cada path contra `project_root`

Depois exige

`candidate.relative_to(root)`

Qualquer escape falha antes de virar candidato

Foram provados

- traversal POSIX
- traversal Windows
- path absoluto fora da raiz

Todos levantam `ValueError`

## Normalização legítima

A segurança não bloqueia uma normalização que continua dentro da raiz

Exemplo

`sub/../inside.py`

resolve para

`inside.py`

e continua elegível

Isso evita transformar canonicalização normal em falso positivo

## Staleness

`evaluate_source_staleness()`

também resolve

`root / metadata.path`

e exige que o resultado permaneça dentro de `repository_root`

Metadata malicioso com

`../outside.py`

é rejeitado antes de leitura

## get_context

Foi criado deliberadamente um índice SQLite contendo um chunk com path malicioso

`../outside.md`

Mesmo o dado já estando no índice

`get_context()`

revalida o path com a política de exclusão e retorna

`RagContextInvalidScopeError`

Isso prova defesa em profundidade

Um índice corrompido ou antigo não transforma path traversal em acesso autorizado

## Git provenance

`capture_git_file_provenance()`

canonicaliza o path contra o root Git

Traversal relativo e path absoluto externo são rejeitados antes do lookup de commit

## Git worktree

`capture_git_path_state()`

aplica a mesma fronteira

Traversal relativo e path absoluto externo são rejeitados antes do `git status`

## Testes negativos

Criado

`tests/test_rag_015_path_traversal.py`

Casos

1. denylist detecta POSIX traversal
2. denylist detecta Windows traversal
3. index plan rejeita POSIX escape
4. index plan rejeita Windows escape
5. index plan rejeita absoluto externo
6. normalização interna continua permitida
7. staleness rejeita metadata externo
8. get_context rejeita path malicioso já indexado
9. Git provenance rejeita escape
10. Git worktree rejeita escape

Execução observada

```text
Ran 7 tests in 0.526s
OK
```

## Alterações de produção

Nenhuma correção adicional foi necessária

As barreiras implementadas em fases anteriores já bloqueavam os vetores testados

RAG-015-C adiciona a prova negativa consolidada exigida para segurança

## Arquivos

Criado

`tests/test_rag_015_path_traversal.py`

Criado

`docs/RAG_015_C_PATH_TRAVERSAL.md`

## Critério de aceitação

RAG-015-C está concluído quando

- POSIX traversal é negado
- Windows traversal é negado
- absoluto externo é negado
- indexação não sai do project_root
- get_context não confia cegamente em path indexado
- staleness não lê fora do root
- Git provenance não sai do root
- Git worktree não sai do root
- canonicalização interna legítima funciona
- testes negativos passam
- suíte RAG passa
- git diff check passa

## Próximo passo

`RAG-015-D — Conteúdo indexado`

Provar que todo chunk possui origem rastreável e que chunks sem proveniência mínima não entram no contrato de indexação
