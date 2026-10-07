# RAG-006-C — Carregamento sob demanda

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-006-jina-text`

## Objetivo

Implementar o lifecycle explícito do modelo textual exigido pelo handoff

```text
UNLOADED
↓
LOADING
↓
READY
↓
IDLE
↓
UNLOADING
↓
UNLOADED
```

RAG-006-C controla somente o processo e a disponibilidade local do backend

Embedding textual pertence ao RAG-006-D

CPU fallback real pertence ao RAG-006-F

Benchmark pertence ao RAG-006-G

## Processo

O backend continua

`llama.cpp HTTP local`

O processo é iniciado diretamente por Python com

`subprocess.Popen`

Regras

- shell=False
- stdin DEVNULL
- stdout e stderr em log próprio
- bind obrigatório 127.0.0.1
- PID mantido pelo lifecycle
- sem `start /b`
- sem terminal interativo como dono do processo

## Smoke manual pré-implementação

Um teste manual com `start /b` mostrou que o processo podia reter o terminal controlador

O teste foi cancelado via CodeBridge e não deixou processo órfão

Esse resultado reforçou a decisão de tornar o objeto lifecycle o proprietário direto do `Popen`

## Linha de comando

Formato

```text
llama-server
-m <modelo.gguf>
--embedding
--pooling last
--host 127.0.0.1
--port <porta>
-ngl <camadas>
```

Os flags foram confirmados no `C:\llama\llama-server.exe` existente no ambiente de desenvolvimento

## Porta

`port=0`

significa seleção automática de uma porta livre em loopback

Uma porta fixa também pode ser fornecida explicitamente

A porta resolvida fica no snapshot do lifecycle

## Verificação antes da carga

Antes de iniciar processo

1. llama-server precisa existir
2. GGUF precisa existir
3. GGUF precisa passar novamente pelo tamanho e SHA-256 pinados no RAG-006-B

O lifecycle nunca baixa modelo

## Health

Após o processo iniciar

o estado permanece

`LOADING`

até

`GET /health`

responder HTTP 200

Se o processo encerrar antes disso

a carga falha

Se o timeout expirar

a carga falha

Em ambos os casos

- processo é encerrado se necessário
- handles são fechados
- porta é liberada do objeto
- estado volta para UNLOADED

## READY

READY significa

- processo vivo
- health confirmado
- PID conhecido
- host e porta conhecidos

Chamar `load()` novamente em READY não cria outro processo

## IDLE

`mark_idle()`

muda

`READY → IDLE`

sem descarregar o modelo

`mark_ready()`

permite

`IDLE → READY`

sem reiniciar processo

O idle timeout automático pertence ao RAG-008-C

## UNLOAD

`unload()`

executa

```text
READY ou IDLE
↓
UNLOADING
↓
terminate
↓
wait
↓
kill se timeout
↓
fechar log
↓
remover PID e porta
↓
UNLOADED
```

Unload em UNLOADED é idempotente

## Logs

Se `log_path` não for informado

o padrão em Windows é

```text
%LOCALAPPDATA%\CodeBridge\logs\rag\
jina-v5-text-small\llama-server.log
```

O diretório só é criado durante `load()`

Import e construção do objeto continuam sem side effects

## GPU

O RAG-006-C usa

`gpu_layers=99`

como preferência atual de carga

Isso não é ainda o contrato de fallback

RAG-006-F deverá provar que

- GPU funciona
- falha ou ausência de GPU troca para CPU
- CPU funciona sem depender de CUDA

## Implementação

Criado

`rag/models/lifecycle.py`

API pública

- ModelLifecycleState
- ModelLifecycleSnapshot
- LlamaServerConfig
- TextModelLifecycle
- ModelLifecycleError
- ModelLoadError
- ModelUnloadError
- ModelLifecycleStateError
- build_llama_server_argv
- find_free_loopback_port
- probe_http_health

Atualizado

`rag/models/__init__.py`

Criado

`tests/test_rag_text_model_lifecycle.py`

## Testes unitários

O corpus prova

- estado inicial UNLOADED
- argv correto
- loopback obrigatório
- sequência completa A→F do lifecycle
- IDLE volta a READY sem novo processo
- load READY é idempotente
- unload UNLOADED é idempotente
- health polling
- porta automática
- processo que morre antes do health
- timeout de health
- terminate
- escalada kill
- transições inválidas
- executável ausente
- modelo inválido
- nenhum processo no import ou construtor

## Critério de aceitação

RAG-006-C está concluído quando

- state machine exigida existe
- health gate controla READY
- PID e porta ficam disponíveis
- load não duplica processo
- unload encerra processo
- falha durante load faz rollback
- modelo é revalidado antes da carga
- import permanece sem side effects
- smoke real com modelo instalado passa
- após unload o PID não permanece
- suíte RAG passa
- diff check passa


## Correção encontrada durante a validação

A primeira versão do corpus deixou quatro cenários de sucesso propositalmente em `READY`

Nesses casos o handle do arquivo de log continuava aberto porque o modelo ainda estava carregado

No Windows isso impediu o `TemporaryDirectory` de apagar o log e gerou `WinError 32`

O lifecycle estava correto

Os testes foram corrigidos para chamar `unload()` antes de encerrar cada cenário que deixou processo carregado

Isso também passou a provar fechamento explícito dos recursos em cada caso

## Smoke real com o modelo instalado

O lifecycle foi executado contra

`C:\llama\llama-server.exe`

e o artefato real validado no RAG-006-B

Configuração

```text
host = 127.0.0.1
port = 0
gpu_layers = 99
pooling = last
```

Resultado observado

```text
STATE0=UNLOADED
READY_PID=2912
READY_PORT=57728
READY_HEALTH=http://127.0.0.1:57728/health
STATE1=READY
STATE2=IDLE
STATE3=READY
STATE4=UNLOADED
HISTORY=UNLOADED,LOADING,READY,IDLE,READY,UNLOADING,UNLOADED
PID_STILL_PRESENT=False
```

O PID e a porta são valores do smoke e não são configuração fixa

A porta foi escolhida automaticamente

O health gate confirmou a transição para READY

O mesmo processo foi mantido ao alternar READY e IDLE

Após unload o PID não permaneceu no sistema

## Validação final

Testes específicos do lifecycle

```text
Ran 16 tests
OK
```

Suíte RAG completa

```text
Ran 285 tests
OK
```

Git whitespace audit

```text
git diff --check 7264a6a7846d5eb29e6270daafccc87d23bbcf38..HEAD
exit_code = 0
```

## Estado final do RAG-006-C

- state machine implementada
- modelo real carregado sob demanda
- health local confirmado
- PID conhecido em READY
- porta automática confirmada
- IDLE não descarrega o processo
- retorno IDLE → READY não reinicia o processo
- unload real encerra o processo
- nenhum PID órfão após unload
- modelo é revalidado antes de cada carga
- suíte RAG verde

RAG-006-C está pronto para fechamento
