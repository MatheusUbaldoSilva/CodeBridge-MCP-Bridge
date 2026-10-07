# RAG-008-E — Falhas seguras e fallback lexical

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-008-model-manager`

## Objetivo

Fechar a política inicial de falhas do Model Manager

Requisitos do handoff

- liberar recursos
- retornar erro estruturado
- manter FTS5 disponível
- não derrubar MCP

## API segura

Foram adicionadas duas operações voltadas à fronteira de integração

`activate_safe()`

`unload_active_safe()`

Essas operações convertem falhas de runtime em resultado estruturado em vez de deixar a exceção atravessar a fronteira do Model Manager

Erros de programação como passar um tipo de modelo inválido continuam explícitos com ValueError

## Resultado estruturado

`ModelManagerOperationResult`

contém

- ok
- operation
- requested_model
- active_model
- value em sucesso
- error_type
- error_message
- cause_type
- cleanup_errors
- fallback_route

Tipos estáveis de erro

```text
ACTIVATION_FAILED
UNLOAD_FAILED
```

## Fallback lexical

Toda falha operacional segura retorna

```text
fallback_route = LEXICAL_ONLY
```

Essa rota já foi congelada no RAG-008-A

O Model Manager não abre fecha nem altera o índice FTS5

Assim uma falha de modelo não remove a capacidade lexical existente

A camada de busca pode continuar pelo caminho FTS5 usando a indicação LEXICAL_ONLY

## Limpeza após falha

Quando uma ativação ou unload seguro falha

o manager tenta unload nos dois runtimes

```text
falha operacional
↓
tentar unload TEXT
↓
tentar unload CODE
↓
active_model = None
last_activity_at = None
↓
retornar resultado estruturado
```

A tentativa de limpeza não mascara o erro original

Se alguma limpeza também falhar ela é registrada em

`cleanup_errors`

## Resources released

`resources_released`

é verdadeiro quando nenhuma tentativa de cleanup retornou erro

Se for falso o chamador recebe explicitamente a informação de que a limpeza não foi totalmente confirmada

Mesmo nesse caso o erro é estruturado e não precisa derrubar o MCP

## Segurança da fronteira

O método baixo nível `activate()` continua disponível e pode lançar exceções para testes e integração interna

A fronteira MCP deve preferir `activate_safe()`

Isso separa

- erro de runtime recuperável
- erro de programação
- política de fallback lexical

## Integração com RAG-008-B C D

Continuam válidos

- exclusão mútua TEXT CODE
- idle timeout configurável
- serialização de transições concorrentes

As APIs seguras usam o mesmo RLock do manager

Cleanup também ocorre dentro da mesma operação serializada

## Arquivos

Atualizado

`rag/runtime/model_manager.py`

Atualizado

`rag/runtime/__init__.py`

Criado

`tests/test_rag_model_manager_failure_policy.py`

Criado

`docs/RAG_008_E_FAILURE_POLICY.md`

## Critério de aceitação

RAG-008-E está concluído quando

- load com sucesso retorna resultado estruturado de sucesso
- load com falha não propaga exceção operacional pela API segura
- falha solicita LEXICAL_ONLY
- cleanup dos runtimes é tentado
- erro de cleanup é preservado
- unload com falha também retorna resultado estruturado
- manager não declara modelo ativo após falha segura
- FTS5 não é tocado pelo Model Manager
- testes específicos passam
- suíte RAG passa
- git diff check passa

## Estado esperado após esta fase

Com RAG-008-A B C D E fechados o Model Manager possui

- classificação determinística
- exclusão mútua
- timeout de idle
- serialização de concorrência
- política segura de falhas

O RAG-008 fica pronto para closeout formal
