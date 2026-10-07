# RAG-006-A — Backend de inferência

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-006-jina-text`

## Objetivo

Escolher o backend de inferência do Jina v5 Text Small compatível com

- GPU quando disponível
- CPU fallback
- Windows
- distribuição com CodeBridge

Esta fase é somente decisão e contrato

Nenhum modelo é instalado ou baixado

## Modelo alvo

Família

`jinaai/jina-embeddings-v5-text-small`

Para o uso do CodeBridge o alvo de inferência local passa a ser a variante oficial com adapter de retrieval já fundido

`jinaai/jina-embeddings-v5-text-small-retrieval`

A escolha da variante retrieval é compatível com o objetivo do RAG

- query de busca
- documentos indexados
- embeddings para recuperação semântica

O formato selecionado para o backend é

`GGUF`

A quantização exata não é escolhida no RAG-006-A

## Pesquisa externa verificada em 2026-10-07

### Modelo Jina

A documentação oficial do modelo registra

- 677M parâmetros
- contexto máximo de 32768 tokens
- embedding de 1024 dimensões
- pooling last-token
- suporte a retrieval
- suporte oficial a Transformers e SentenceTransformers

Fonte

https://huggingface.co/jinaai/jina-embeddings-v5-text-small

### Variante retrieval

A Jina publica a variante

`jina-embeddings-v5-text-small-retrieval`

com

- Safetensors
- ONNX
- GGUF
- suporte documentado a llama.cpp
- suporte documentado a Windows por WinGet ou binário prebuilt

A documentação mostra servidor local de embeddings com

`llama-server --embedding --pooling last`

e cliente usando

`/v1/embeddings`

com prompts explícitos

`Query: ...`

`Document: ...`

Fonte

https://huggingface.co/jinaai/jina-embeddings-v5-text-small-retrieval

### llama.cpp

O servidor oficial llama.cpp documenta

- inferência F16 e quantizada em GPU e CPU
- endpoint OpenAI-compatible de embeddings
- Windows
- bind padrão em 127.0.0.1
- seleção de device e GPU offload

Fonte

https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md

### ONNX Runtime

ONNX Runtime também é tecnicamente compatível

A Jina fornece ONNX no repositório retrieval e documenta

- CPUExecutionProvider
- CUDAExecutionProvider

Porém a distribuição GPU em Windows exige coordenar CUDA/cuDNN ou dependências equivalentes

Fonte

https://onnxruntime.ai/docs/install/

## Ambiente real observado

Consultado pelo CodeBridge em 2026-10-07

```text
GPU:
NVIDIA GeForce RTX 3050 6GB Laptop GPU
VRAM: 6144 MiB
driver: 577.05

Python:
3.13.15

Pacotes no ambiente Python atual:
torch = ausente
transformers = ausente
sentence_transformers = ausente
onnxruntime = ausente
optimum = ausente

llama-server no PATH:
não

arquivo existente:
C:\llama\llama-server.exe
```

A existência desse executável é evidência ambiental

O CodeBridge não dependerá desse caminho específico em produção

## Backends avaliados

### 1 — llama.cpp local HTTP

Status

**SELECIONADO**

Características

- GPU suportada
- CPU suportada
- Windows suportado
- GGUF oficial disponível para o modelo retrieval
- servidor OpenAI-compatible
- processo pode ser carregado e encerrado isoladamente
- não exige transformar o Python principal do CodeBridge em ambiente ML

Modo de distribuição pretendido

`BUNDLED_SIDECAR`

O executável será resolvido por configuração/runtime futuro

Não existe hardcode de `C:\llama`

### 2 — PyTorch + SentenceTransformers

Status

COMPATÍVEL MAS NÃO SELECIONADO

É a implementação de referência mais direta do modelo

Vantagens

- suporte oficial Jina
- CUDA
- CPU
- task e prompt integrados

Custo para CodeBridge

- torch
- transformers
- PEFT
- sentence-transformers opcional
- ambiente Python ML pesado

Como o Python atual não possui nenhuma dessas dependências essa rota aumentaria fortemente o pacote e o acoplamento

Ela permanece alternativa técnica caso benchmark futuro mostre necessidade

### 3 — ONNX Runtime + Optimum

Status

COMPATÍVEL MAS NÃO SELECIONADO

Vantagens

- modelo ONNX oficial já publicado
- CPUExecutionProvider
- CUDAExecutionProvider
- bom caminho potencial de produção

Motivo para não selecionar agora

- mais complexidade de provider CUDA/cuDNN em Windows
- ainda exige tokenizer e pooling corretos
- não há benefício comprovado antes do benchmark
- adicionaria nova stack Python ao CodeBridge

Pode ser reavaliado somente com benchmark objetivo

## Política congelada

Backend

`LLAMA_CPP_HTTP`

Modelo lógico

`jinaai/jina-embeddings-v5-text-small-retrieval`

Formato

`GGUF`

Transport

`HTTP_OPENAI_COMPATIBLE`

Bind obrigatório

`127.0.0.1`

Endpoint de embeddings

`/v1/embeddings`

Health

`/health`

Pooling

`last`

Prompts

```text
query    = "Query: " + texto
document = "Document: " + texto
```

Política de dispositivo

```text
GPU preferida
↓
se indisponível ou falhar
↓
CPU fallback obrigatório
```

A implementação concreta do fallback será provada no RAG-006-F

## Segurança

O servidor de embeddings deve ser local

`127.0.0.1`

Não será exposto em `0.0.0.0` por padrão

Nenhum download pode ocorrer no import

Nenhum processo pode iniciar no import

Nenhuma GPU pode ser aberta no import

Nenhum backend ML Python é carregado no import

## Licença do modelo

O modelo oficial está publicado sob

`CC-BY-NC-4.0`

A documentação da Jina informa que uso comercial exige contato/licença apropriada

Portanto

`model_bundling_allowed = false`

permanece congelado no RAG-006-A

O RAG-006-B deverá tratar explicitamente

- origem
- revisão
- hash
- arquivo
- tamanho
- diretório
- licença
- aceite/autorização aplicável

O CodeBridge não embutirá o modelo silenciosamente

## Fronteira com RAG-006-B

Ainda NÃO estão definidos

- revisão Hugging Face
- nome do GGUF
- quantização
- SHA-256
- tamanho
- diretório local definitivo
- rotina de download
- aceite do usuário

Todos pertencem ao RAG-006-B

## Fronteira com RAG-006-C

Ainda NÃO existe lifecycle

```text
UNLOADED
LOADING
READY
IDLE
UNLOADING
```

RAG-006-C será responsável por

- resolver o executável autorizado
- iniciar llama-server com argv explícito
- escolher porta local
- health check
- armazenar PID
- encerrar o processo
- liberar recursos

## Implementação

Criado

`rag/models/backend_policy.py`

API pública

- InferenceBackend
- DistributionMode
- BackendEvaluation
- ModelArtifactPin
- TextEmbeddingBackendPolicy
- BACKEND_EVALUATIONS
- SELECTED_TEXT_BACKEND
- selected_backend_evaluation

Criado

`rag/models/__init__.py`

## Testes

Criado

`tests/test_rag_text_backend_policy.py`

O corpus prova

- um único backend selecionado
- GPU CPU Windows e distribuição avaliados
- llama.cpp selecionado
- Python ML não obrigatório no backend selecionado
- variante retrieval congelada
- loopback local
- endpoint de embeddings
- last-token pooling
- prompts Query e Document
- GPU preferida e CPU fallback obrigatório
- modelo ainda não pinado
- nenhum download permitido
- licença exige revisão
- import não carrega torch transformers ONNX ou llama bindings
- import não abre rede nem processo

## Critério de aceitação

RAG-006-A está concluído quando

- backend está explicitamente selecionado
- GPU e CPU estão no contrato
- Windows está no contrato
- distribuição do CodeBridge está definida
- nenhuma dependência pesada é instalada nesta fase
- nenhum modelo é baixado
- revisão hash e quantização permanecem para RAG-006-B
- suíte RAG passa
- diff check passa
