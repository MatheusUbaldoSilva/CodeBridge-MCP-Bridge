# RAG-007-B — Artefato pinado e carregamento sob demanda

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-007-jina-code`

## Objetivo

Pinar um GGUF exato do Jina Code Embeddings 1.5B, instalar de forma controlada e reutilizar a state machine já provada no RAG-006.

## Artefato selecionado

Repository

`jinaai/jina-code-embeddings-1.5b-GGUF`

Revision imutável

`67f160ae7d22bb80dc6273cedcc67c027f430c9d`

Filename

`jina-code-embeddings-1.5b-Q8_0.gguf`

Quantization

`Q8_0`

Size

`1646569888 bytes`

SHA-256

`3a09a8817b852b5a4faaa6ebb1a5590322746d2b570b578d0b7e3b6e849062aa`

Licença

`CC-BY-NC-4.0`

## Motivo da escolha Q8_0

O repositório oficial oferece quantizações menores, incluindo IQ4.

Para o primeiro índice de código, foi escolhido Q8_0 para priorizar fidelidade de embedding.

O arquivo possui aproximadamente 1.53 GiB, tamanho compatível com a GPU de 6 GiB usada no ambiente de desenvolvimento.

A adequação real de VRAM será provada por carga real e posteriormente medida formalmente no RAG-007-G.

## Download

Download automático continua desligado.

A instalação exige simultaneamente

- `allow_download=True`
- `license_acknowledged=True`

O instalador genérico e atômico do RAG-006 é reutilizado.

Não existe uma segunda implementação de download.

## Destino

```text
%LOCALAPPDATA%\CodeBridge\models\
jina-code-embeddings-1.5b\
67f160ae7d22bb80dc6273cedcc67c027f430c9d\
jina-code-embeddings-1.5b-Q8_0.gguf
```

## Validação

Antes de qualquer carga real

- tamanho precisa ser exatamente 1646569888 bytes;
- SHA-256 precisa ser exatamente o pinado;
- arquivo parcial não é promovido;
- arquivo existente incorreto não é sobrescrito silenciosamente.

## State machine

RAG-007-B reutiliza

```text
UNLOADED
→ LOADING
→ READY
→ IDLE
→ READY
→ UNLOADING
→ UNLOADED
```

Não existe uma segunda implementação de state machine.

`CodeModelLifecycle` herda o lifecycle já validado e troca somente a validação do artefato e o diretório de log.

## Configuração inicial de servidor

```text
--embedding
--pooling last
--ctx-size 8192
--ubatch-size 8192
--host 127.0.0.1
--port <automática>
-ngl 99
```

O device GPU será descoberto no smoke real.

Se 8192 de ubatch não couber de forma estável, o valor operacional será reduzido com evidência real e documentado, sem alterar o limite lógico de contexto.

## Extensão compatível do lifecycle

`LlamaServerConfig` passou a aceitar opcionalmente

- `context_size`
- `ubatch_size`

Quando ausentes, o modelo textual do RAG-006 continua produzindo exatamente o argv anterior.

## Implementação

Atualizado

- `rag/models/code_backend_policy.py`
- `rag/models/lifecycle.py`
- `rag/models/__init__.py`
- `tests/test_rag_code_backend_policy.py`

Criado

- `rag/models/code_artifact_install.py`
- `rag/models/code_lifecycle.py`
- `tests/test_rag_code_artifact_install.py`
- `tests/test_rag_code_model_lifecycle.py`

## Critério de aceitação

RAG-007-B fecha quando

- Q8_0 está pinado por revisão/tamanho/SHA;
- instalação controlada funciona;
- modelo real passa verificação;
- modelo real chega a READY;
- IDLE e retorno READY funcionam;
- unload retorna UNLOADED;
- PID não permanece;
- dimensão real da resposta é observada e registrada;
- suíte RAG passa;
- diff check passa.


## Instalação real validada

A instalação foi executada pelo próprio `install_selected_code_model`.

Resultado

```text
DOWNLOADED=True
SIZE=1646569888
SHA256=3a09a8817b852b5a4faaa6ebb1a5590322746d2b570b578d0b7e3b6e849062aa
REVISION=67f160ae7d22bb80dc6273cedcc67c027f430c9d
FILENAME=jina-code-embeddings-1.5b-Q8_0.gguf
```

Destino real

```text
C:\Users\Matheus\AppData\Local\CodeBridge\models\
jina-code-embeddings-1.5b\
67f160ae7d22bb80dc6273cedcc67c027f430c9d\
jina-code-embeddings-1.5b-Q8_0.gguf
```

O arquivo final só foi promovido depois de tamanho e SHA-256 conferirem com o manifesto pinado.

## Smoke real do lifecycle de código

Ambiente

```text
llama-server = C:\llama\llama-server.exe
device = CUDA0
ctx-size = 8192
ubatch-size = 8192
gpu-layers = 99
pooling = last
```

Resultado

```text
STATE0=UNLOADED
DEVICE=CUDA0
PID=5872
PORT=56619
STATE1=READY
STATE2=IDLE
STATE3=READY
DIM=1536
NORM=1.000000025
STATE4=UNLOADED
HISTORY=UNLOADED,LOADING,READY,IDLE,READY,UNLOADING,UNLOADED
```

O valor `8192/8192` carregou de primeira no ambiente real e não precisou ser reduzido.

O PID e a porta acima são somente os valores do smoke.

Uma checagem posterior

```text
tasklist /FI "PID eq 5872"
```

retornou

```text
INFORMAÇÕES: nenhuma tarefa em execução correspondente aos critérios especificados.
```

Portanto o unload não deixou o processo residente.

## Dimensão real observada

A documentação oficial do GGUF atualmente contém uma nota dizendo que llama.cpp retorna 896 dimensões para este modelo.

O smoke real do Q8_0 com

```text
llama.cpp 0.4.0-dev
build 10819
commit 6a1a922d2
```

retornou

`1536`

dimensões.

RAG-007-B registra essa evidência sem substituir silenciosamente a documentação upstream.

A dimensão efetiva será congelada no contrato de embedding do RAG-007-C com testes próprios.

## Validação final

Testes específicos da fase + regressão do lifecycle textual

```text
Ran 37 tests
OK
```

Suíte RAG completa

```text
Ran 350 tests
OK
```

Git whitespace audit

```text
git diff --check 7e59a1b7e3a79ce4be61b3df0f6a0be2a591a1ab..HEAD
exit_code = 0
```

Worktree

```text
## HEAD (no branch)
```

sem alterações locais.

## Estado final do RAG-007-B

- Q8_0 pinado por revisão imutável;
- tamanho e SHA-256 pinados;
- instalação atômica reutilizada;
- instalação real validada;
- ctx-size 8192 validado;
- ubatch-size 8192 validado;
- GPU CUDA0 carregou o modelo;
- health gate chegou a READY;
- IDLE → READY funcionou;
- embedding HTTP respondeu;
- dimensão real observada em 1536;
- norma unitária observada;
- unload retornou UNLOADED;
- PID não permaneceu;
- 350 testes RAG passaram;
- diff check passou.

RAG-007-B está pronto para fechamento.
