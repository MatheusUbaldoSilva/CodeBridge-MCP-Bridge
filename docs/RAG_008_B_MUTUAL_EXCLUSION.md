# RAG-008-B — Exclusão mútua inicial dos modelos

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-008-model-manager`

## Objetivo

Garantir por padrão que o modelo textual e o modelo de código não permaneçam residentes ao mesmo tempo

Requisito do handoff

- não manter os dois modelos pesados residentes ao mesmo tempo
- carregar somente o necessário
- permitir exceção futura somente após benchmark

## Implementação

Criado

`rag/runtime/model_manager.py`

Atualizado

`rag/runtime/__init__.py`

Criado

`tests/test_rag_model_manager_mutual_exclusion.py`

## Contrato

O manager conhece somente dois alvos

```text
TEXT
CODE
```

Estado inicial

```text
active_model = None
text_loaded = False
code_loaded = False
```

## Troca TEXT → CODE

Fluxo obrigatório

```text
TEXT ativo
↓
unload TEXT
↓
estado sem modelo residente
↓
load CODE
↓
CODE ativo
```

O load do CODE nunca começa antes do unload do TEXT terminar

## Troca CODE → TEXT

Fluxo obrigatório

```text
CODE ativo
↓
unload CODE
↓
estado sem modelo residente
↓
load TEXT
↓
TEXT ativo
```

## Reativação do mesmo modelo

Se o modelo solicitado já for o ativo

- o runtime ativo recebe load novamente
- o outro runtime não é tocado
- a idempotência continua responsabilidade do lifecycle existente

## Falha no load após troca

Se o modelo anterior já foi descarregado e o novo load falha

- o erro original é propagado
- active_model volta para None
- o manager não declara nenhum modelo residente

A política estruturada de recuperação de falhas pertence ao RAG-008-E

## Unload explícito

`unload_active()`

descarrega somente o runtime ativo

Mesmo se o unload lançar exceção o estado interno do manager deixa de declarar o modelo como residente

A política de erro estruturado continua fora desta fase

## Invariantes

`ModelManagerSnapshot` rejeita estado impossível onde TEXT e CODE aparecem residentes simultaneamente

Também rejeita active_model inconsistente com os flags de residência

## Escopo preservado

RAG-008-B não implementa

- idle timeout
- locks
- concorrência
- duas cargas simultâneas
- recuperação estruturada de falhas
- fallback FTS5
- execução HYBRID simultânea
- exceção permitindo os dois modelos residentes

Esses pontos ficam para RAG-008-C D E ou benchmark futuro aprovado

## Critério de aceitação

RAG-008-B está concluído quando

- TEXT sozinho pode ser ativado
- CODE sozinho pode ser ativado
- TEXT → CODE descarrega TEXT antes de carregar CODE
- CODE → TEXT descarrega CODE antes de carregar TEXT
- nunca existe snapshot válido com os dois residentes
- falha de load não deixa o manager declarando um modelo ativo incorretamente
- unload explícito limpa o estado de residência
- testes específicos passam
- suíte RAG passa
- git diff check passa
