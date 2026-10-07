# RAG-008-C — Idle timeout configurável

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-008-model-manager`

## Objetivo

Adicionar timeout de inatividade configurável ao Model Manager sem antecipar concorrência ou criar thread em background

Requisito do handoff

`Timeout configurável`

## Estratégia

O timeout é cooperativo

O Model Manager registra a última atividade e expõe

`unload_if_idle()`

Nenhuma thread é criada nesta fase

Nenhum timer roda no import

Nenhum modelo é carregado automaticamente

Isso mantém RAG-008-C separado do controle de concorrência do RAG-008-D

## Configuração

Novo parâmetro

`idle_timeout_seconds`

Valores válidos

- `None` desabilita unload automático por idle
- número maior que zero habilita a política

Zero e valores negativos são rejeitados

## Atividade

A atividade é atualizada quando

- TEXT é carregado
- CODE é carregado
- o mesmo modelo é reativado
- `touch()` é chamado explicitamente

A troca de TEXT para CODE ou CODE para TEXT reinicia o relógio somente após o novo modelo carregar com sucesso

## Verificação

`idle_seconds()`

retorna o tempo de inatividade do modelo ativo

`unload_if_idle()`

faz

```text
sem timeout configurado
→ não descarrega

sem modelo ativo
→ não descarrega

idle < timeout
→ mantém modelo

idle >= timeout
→ unload do modelo ativo
→ active_model = None
→ last_activity_at = None
```

## Clock

Por padrão é usado

`time.monotonic`

O clock é injetável para testes determinísticos

Nenhum teste depende de sleep real

## Integração com exclusão mútua

A regra do RAG-008-B continua válida

Nunca existe estado válido com TEXT e CODE residentes simultaneamente

O idle timeout age somente sobre o único modelo ativo

## Arquivos

Atualizado

`rag/runtime/model_manager.py`

Criado

`tests/test_rag_model_manager_idle_timeout.py`

Criado

`docs/RAG_008_C_IDLE_TIMEOUT.md`

## Fronteiras

RAG-008-C não implementa

- locks
- proteção contra duas chamadas simultâneas
- single flight
- fila de loads
- recuperação estruturada de falhas
- fallback FTS5
- thread de manutenção em background

Concorrência pertence ao RAG-008-D

Falhas pertencem ao RAG-008-E

## Critério de aceitação

RAG-008-C está concluído quando

- timeout é configurável
- timeout desabilitado preserva modelo
- atividade inicia relógio
- touch renova relógio
- antes do limite não ocorre unload
- no limite ocorre unload
- TEXT e CODE obedecem a mesma política
- troca de modelo reinicia atividade
- unload limpa timestamp
- testes específicos passam
- suíte RAG passa
- git diff check passa
