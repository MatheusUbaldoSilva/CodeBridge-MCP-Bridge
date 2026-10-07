# RAG-006-B — Download e instalação controlada

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-006-jina-text`

## Objetivo

Congelar o artefato exato do Jina v5 Text Small Retrieval e implementar instalação local verificável sem download silencioso

## Artefato selecionado

Repositório oficial

`jinaai/jina-embeddings-v5-text-small-retrieval`

Revisão imutável

`e9137ac0a9d41c851de69bea36babc029b7f5fc9`

Arquivo

`v5-small-retrieval-Q4_K_M.gguf`

Quantização

`Q4_K_M`

Tamanho exato

`396705152 bytes`

SHA-256

`9440cf89f3e8a7a31a42e11b87e106dd5b344af4e0e3b6b21a96136cc8686e21`

Licença

`CC-BY-NC-4.0`

## Evidência externa

Os metadados foram confirmados em 2026-10-07 por duas fontes

1. página oficial do arquivo no Hugging Face
2. requisição HTTP HEAD ao URL imutável de resolve

O HEAD devolveu

```text
X-Repo-Commit:
e9137ac0a9d41c851de69bea36babc029b7f5fc9

X-Linked-ETag:
9440cf89f3e8a7a31a42e11b87e106dd5b344af4e0e3b6b21a96136cc8686e21

Content-Length:
396705152
```

A URL de download é construída com essa revisão

Nunca usa `resolve/main`

## Motivo do Q4_K_M

Q4_K_M é usado nos exemplos oficiais de llama.cpp do próprio repositório Jina

Para o alvo atual

- RTX 3050 Laptop 6 GB
- CPU fallback obrigatório
- modelo 677M
- backend llama.cpp

ele é o ponto inicial aprovado antes de benchmark

Quantizações diferentes só poderão substituir esse pin após benchmark e novo hash explícito

## Diretório local

Padrão

```text
%LOCALAPPDATA%\CodeBridge\models\
  jina-v5-text-small-retrieval\
    e9137ac0a9d41c851de69bea36babc029b7f5fc9\
      v5-small-retrieval-Q4_K_M.gguf
```

A revisão faz parte do path

Isso evita sobrescrever silenciosamente uma versão por outra

Nenhum diretório é criado durante import ou simples resolução do path

## Download controlado

A API exige simultaneamente

`allow_download=True`

e

`license_acknowledged=True`

Sem qualquer uma dessas duas condições

- nenhuma conexão é aberta
- nenhum diretório é criado
- nenhum arquivo parcial é criado

## Download atômico

O fluxo é

```text
URL imutável
↓
arquivo .partial
↓
contagem de bytes
↓
SHA-256 streaming
↓
comparação com manifest
↓
fsync
↓
os.replace
↓
arquivo final
```

O target final só aparece após validação integral

## Falhas

Se o download

- exceder o tamanho pinado
- terminar com tamanho diferente
- terminar com SHA diferente
- levantar exceção de rede ou disco

o arquivo parcial é removido

O arquivo final não é publicado

## Arquivo existente

Se já existir e for válido

- é reutilizado
- nenhuma rede é usada

Se existir e for inválido

- instalação falha
- arquivo não é sobrescrito silenciosamente

A política de reparo explícito poderá ser adicionada depois

## Segurança e licença

`auto_download_allowed=False`

continua congelado

`model_bundling_allowed=False`

continua congelado

O modelo não entra no instalador do CodeBridge nesta fase

O uso comercial continua condicionado à revisão de licença já registrada no RAG-006-A

## Implementação

Atualizado

`rag/models/backend_policy.py`

Criado

`rag/models/artifact_install.py`

Atualizado

`rag/models/__init__.py`

Criado

`tests/test_rag_model_artifact_install.py`

Atualizado

`tests/test_rag_text_backend_policy.py`

## Testes

O corpus usa artefatos pequenos em memória

Nenhum teste baixa o GGUF real

São provados

- manifest completo
- revisão imutável
- URL sem main
- path revisionado
- ausência de side effect na resolução
- consentimento obrigatório
- aceite da licença obrigatório
- download atômico
- verificação SHA-256
- verificação de tamanho
- cleanup de partial
- reuso de arquivo válido
- recusa de arquivo inválido existente
- auto download permanece desligado

## Fronteira com download real

O código de instalação fica pronto e testado antes do primeiro download real

O download real só pode ocorrer em uma chamada explícita com os dois gates habilitados

## Critério de aceitação

RAG-006-B está concluído quando

- origem está congelada
- revisão imutável está congelada
- arquivo e quantização estão congelados
- tamanho exato está congelado
- SHA-256 está congelado
- diretório está congelado
- licença está visível
- download exige consentimento explícito
- instalação é atômica
- hash e tamanho são verificados
- nenhuma rede ocorre no import
- suíte RAG passa
- diff check passa


## Instalação real validada no Windows

Após o código e os testes passarem, foi executada uma instalação real usando exatamente os dois gates explícitos

```text
allow_download=True
license_acknowledged=True
```

Essa autorização foi aplicada somente para instalação local de desenvolvimento

Ela não altera

`auto_download_allowed=False`

nem

`model_bundling_allowed=False`

Resultado final verificado localmente

```text
PATH=C:\Users\Matheus\AppData\Local\CodeBridge\models\
jina-v5-text-small-retrieval\
e9137ac0a9d41c851de69bea36babc029b7f5fc9\
v5-small-retrieval-Q4_K_M.gguf

EXISTS=True
VALID=True
SIZE=396705152
SHA256=9440cf89f3e8a7a31a42e11b87e106dd5b344af4e0e3b6b21a96136cc8686e21
```

O download foi iniciado pelo instalador controlado do próprio RAG-006-B

A resposta do terminal expirou durante a transferência, então nenhum segundo download foi disparado

O estado do CodeBridge mostrou o PowerShell ainda executando

Após o terminal finalizar a validação foi feita em leitura somente pelo CMD

O arquivo final corresponde exatamente ao manifest pinado

Nenhum arquivo parcial permaneceu como target final

## Resultado de testes reais

Testes específicos de backend + instalação

```text
Ran 27 tests
OK
```

Suíte RAG completa

```text
Ran 269 tests
OK
```

Git whitespace audit

```text
git diff --check d61d279a92d839fa402f5f254a8f13ac13ee7bf0..HEAD
exit_code = 0
```

## Estado final do RAG-006-B

- artefato imutavelmente pinado
- Q4_K_M selecionado
- tamanho exato pinado
- SHA-256 pinado
- diretório revisionado
- download automático desligado
- bundling desligado
- licença visível
- instalação real concluída
- arquivo real validado
- suíte RAG verde

RAG-006-B está pronto para fechamento
