# RAG-008-D — Concorrência do Model Manager

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-008-model-manager`

## Objetivo

Evitar duas cargas simultâneas do mesmo modelo e impedir transições concorrentes que possam quebrar a exclusão mútua

Requisito do handoff

`Evitar duas cargas simultâneas do mesmo modelo`

## Estratégia

O Model Manager passa a usar um único `threading.RLock` para serializar transições de estado

São serializados

- activate
- unload_active
- unload_if_idle
- touch
- leitura do snapshot
- leitura do active_model
- leitura do last_activity_at
- cálculo de idle_seconds

O lock é reentrante porque `unload_if_idle` chama métodos que também são protegidos

## Mesmo modelo

Se duas threads pedirem TEXT ao mesmo tempo

```text
thread 1
↓
adquire lock
↓
load TEXT

thread 2
↓
aguarda lock
↓
somente depois do primeiro load terminar pode entrar
```

O mesmo vale para CODE

A segunda ativação ainda pode chamar o lifecycle novamente depois da primeira terminar

Isso preserva a semântica idempotente já adotada no RAG-008-B

O requisito desta fase é impedir sobreposição simultânea dos loads

## Modelos diferentes

Se TEXT estiver carregando e outra thread pedir CODE

CODE não começa enquanto a transição TEXT não terminar

Depois

```text
TEXT load termina
↓
TEXT fica ativo
↓
segunda thread entra
↓
unload TEXT
↓
load CODE
```

Assim a exclusão mútua continua válida mesmo com chamadas concorrentes

## Unload concorrente

Se uma thread pedir unload enquanto outra ainda carrega um modelo

o unload espera a carga terminar

Isso impede unload parcial durante uma transição de load

## Sem side effects no import

Criar o manager apenas cria o lock

Não inicia thread

Não inicia worker

Não cria timer

Não carrega modelo

## Arquivos

Atualizado

`rag/runtime/model_manager.py`

Criado

`tests/test_rag_model_manager_concurrency.py`

Criado

`docs/RAG_008_D_CONCURRENCY.md`

## Fronteiras

RAG-008-D não implementa

- fila persistente
- worker dedicado
- prioridade entre TEXT e CODE
- cancelamento de load
- erro estruturado
- fallback FTS5
- recuperação automática após falha

Esses comportamentos não são necessários para cumprir a concorrência inicial do handoff

A política de falhas pertence ao RAG-008-E

## Critério de aceitação

RAG-008-D está concluído quando

- duas ativações simultâneas do mesmo modelo nunca executam load ao mesmo tempo
- troca TEXT → CODE concorrente permanece serializada
- unload não ocorre no meio de um load
- exclusão mútua do RAG-008-B continua válida
- idle timeout do RAG-008-C continua válido
- testes específicos passam
- suíte RAG passa
- git diff check passa
