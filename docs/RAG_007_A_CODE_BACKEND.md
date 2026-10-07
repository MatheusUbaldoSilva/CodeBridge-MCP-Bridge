# RAG-007-A — Backend do Jina Code 1.5B

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-007-jina-code`

## Objetivo

Validar a compatibilidade real do Jina Code Embeddings 1.5B com o backend escolhido antes de baixar qualquer artefato.

## Modelo oficial

Modelo base de embedding

`jinaai/jina-code-embeddings-1.5b`

GGUF oficial

`jinaai/jina-code-embeddings-1.5b-GGUF`

Base architecture

`Qwen/Qwen2.5-Coder-1.5B`

Licença

`CC-BY-NC-4.0`

Revisão comercial continua obrigatória antes de distribuição.

## Backend selecionado

`LLAMA_CPP_HTTP`

Motivos:

- existe GGUF oficial mantido pela Jina;
- a própria documentação oficial fornece comandos para llama.cpp;
- suporta `llama-server`;
- suporta `/v1/embeddings`;
- suporta GPU e CPU;
- mantém inferência fora do runtime Python principal do CodeBridge;
- reutiliza o sidecar já validado no RAG-006.

## Contrato HTTP

Host de produção

`127.0.0.1`

Endpoint

`/v1/embeddings`

Health

`/health`

Pooling obrigatório

`last`

## Contexto

Máximo documentado

`32768`

Recomendação operacional do GGUF

`<= 8192`

ubatch recomendado

`<= 8192`

RAG-007-A congela inicialmente

```text
recommended_context_tokens = 8192
recommended_ubatch_size = 8192
```

O benchmark de memória continua pertencendo ao RAG-007-G.

## Instruções de tarefa

### NL → Code

Query

```text
Find the most relevant code snippet given the following query:
```

Passage

```text
Candidate code snippet:
```

### Code → Code

Query

```text
Find an equivalent code snippet given the following code snippet:
```

Passage

```text
Candidate code snippet:
```

Também são preservadas as instruções oficiais para

- qa
- code2nl
- code2completion

## Dimensão — divergência que NÃO será escondida

A descrição do modelo de referência declara vetor de 1536 dimensões.

A documentação oficial do GGUF registra explicitamente que o llama.cpp retorna 896 dimensões para este modelo.

Portanto RAG-007-A não força uma dimensão por suposição.

O contrato registra

```text
reference_embedding_dimension = 1536
llama_cpp_documented_dimension = 896
dimension_probe_required = true
```

A dimensão efetiva do artefato escolhido será provada com o modelo real no carregamento/embedding antes de congelar o RAG-007-C.

## Probe do llama.cpp local

Executado no Windows real

```text
C:\llama\llama-server.exe --version
```

Resultado

```text
version: 0.4.0-dev
build 10819
commit 6a1a922d2
Clang 20.1.8
Windows x86_64
```

O help local confirmou todas as capacidades necessárias

- `--embedding`
- `--pooling`
- `--ctx-size`
- `--ubatch-size`
- `--hf-repo`
- `--hf-file`
- `--device`
- `--gpu-layers`

## Probe versionado

Criado

`probe_llama_cpp_code_backend`

Ele executa somente

- `llama-server --version`
- `llama-server --help`

com

- `shell=False`
- timeout
- captura de stdout/stderr

Ele NÃO

- carrega modelo;
- acessa Hugging Face;
- baixa artefato;
- cria processo persistente;
- altera arquivos.

## Download deliberadamente bloqueado

RAG-007-A não escolhe ainda arquivo/quantização.

O artifact pin permanece incompleto.

```text
download_allowed = false
auto_download_allowed = false
model_bundling_allowed = false
```

A escolha de arquivo, revisão imutável, tamanho e SHA-256 pertence ao RAG-007-B.

## Implementação

Criado

`rag/models/code_backend_policy.py`

Atualizado

`rag/models/__init__.py`

Criado

`tests/test_rag_code_backend_policy.py`

## Critério de aceitação

RAG-007-A está concluído quando

- GGUF oficial foi confirmado;
- llama.cpp é backend oficialmente suportado pelo modelo;
- backend local possui todas as flags necessárias;
- pooling last está congelado;
- prefixes de tarefa estão congelados;
- divergência 1536 vs 896 está explícita;
- download permanece bloqueado;
- nenhuma quantização foi escolhida prematuramente;
- testes passam;
- diff check passa.
