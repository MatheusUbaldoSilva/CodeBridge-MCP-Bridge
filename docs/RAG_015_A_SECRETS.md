# RAG-015-A — Secrets

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-015-security`

## Objetivo

Impedir que arquivos sensíveis e conteúdo com credenciais entrem no índice RAG

Requisito do handoff

`Denylist e detecção de arquivos sensíveis`

A política agora possui duas camadas independentes

```text
path denylist
↓
content secret scan
↓
allowlist de fonte
↓
candidato de indexação
```

## Camada 1 — denylist por caminho

A política existente continua sendo executada primeiro

Exemplos já negados

- `.env`
- credentials e secrets por nome
- private keys por nome ou extensão
- token/api-key por nome
- backups
- temporários
- caches
- binários
- `.git/objects`
- virtualenv
- node_modules
- build/dist
- path traversal

O denylist continua tendo precedência sobre as allowlists de código e documentos

## Camada 2 — detecção de conteúdo

Criado

`rag/sources/secret_detection.py`

O scanner é propositalmente conservador

Ele detecta formatos de alta confiança e não usa uma heurística genérica de entropia que marcaria hashes IDs e código normal como segredo

Categorias

```text
PRIVATE_KEY
OPENAI_KEY
GITHUB_TOKEN
AWS_ACCESS_KEY
GOOGLE_API_KEY
SLACK_TOKEN
SECRET_ASSIGNMENT
```

## Private keys

Cabeçalhos reconhecidos

```text
-----BEGIN PRIVATE KEY-----
-----BEGIN RSA PRIVATE KEY-----
-----BEGIN EC PRIVATE KEY-----
-----BEGIN DSA PRIVATE KEY-----
-----BEGIN OPENSSH PRIVATE KEY-----
```

## Tokens de provedores

São reconhecidos formatos de alta confiança

- OpenAI
- GitHub
- AWS access key id
- Google API key
- Slack token

A detecção é feita pelo formato

O valor bruto não é preservado no finding

## Assignments sensíveis

Assignments explícitos para nomes como

- password
- passwd
- api_key
- access_token
- refresh_token
- auth_token
- client_secret
- secret_key
- private_key
- credentials

podem ser classificados como `SECRET_ASSIGNMENT`

Para reduzir falso positivo

- literal quoted precisa ter tamanho mínimo
- bare value precisa conter letras e números
- referências runtime não são tratadas como secret
- placeholders conhecidos não são tratados como secret

Exemplos seguros

```text
api_key = "<REDACTED>"
api_key = "$" + "{CODEBRIDGE_API_KEY}"
client_secret = os.getenv("CLIENT_SECRET")
api_key = process.env.API_KEY
password = None
TOKEN = "TOKEN"
CREDENTIAL = "CREDENTIAL"
```

## Findings não vazam segredo

`SensitiveContentFinding`

guarda somente

```text
kind
line_number
fingerprint
```

O fingerprint é SHA-256 truncado para 12 hex

O secret original não é armazenado no finding nem retornado em `to_dict()`

Isso permite auditoria sem reexpor a credencial detectada

## Integração com indexação

`plan_rag_index()`

agora executa o content scan antes de aceitar um arquivo elegível

Quando um arquivo de nome aparentemente seguro contém secret

```text
denied_count += 1
sensitive_count += 1
arquivo não entra em candidates
```

Foi adicionado ao contrato

`RagIndexPlan.sensitive_count`

e ao `to_dict()`

Assim a superfície MCP pode informar a quantidade bloqueada sem divulgar o conteúdo sensível

## Ordem de segurança

A ordem é importante

### Primeiro

`classify_denied_path()`

Se o path já é proibido o conteúdo nem precisa ser usado para justificar a negação

### Depois

Apenas fontes que seriam elegíveis no scope solicitado são lidas para secret scan

### Finalmente

Somente conteúdo aprovado vira `RagIndexCandidate`

## Testes negativos

Criado

`tests/test_rag_secret_detection.py`

As provas incluem

- private key em arquivo de conteúdo
- token OpenAI formatado
- token GitHub formatado
- AWS access key
- Google API key
- Slack token
- assignment de client_secret
- arquivo `config.py` com secret realista é removido do plano
- `.env` continua negado pelo path denylist
- raw secret não aparece no payload do finding

## Testes de falso positivo

Também são provados como seguros

- placeholders
- variáveis de ambiente
- `os.getenv()`
- `process.env`
- `None`
- labels de Enum como `TOKEN = "TOKEN"`
- hashes SHA-256
- request IDs
- model IDs

## Auditoria no repositório atual

Depois de remover falsos positivos determinísticos

```text
CANDIDATES 343
DENIED 9259
SENSITIVE 0
UNSUPPORTED 72
```

Isso significa que nenhum candidato atual do repositório foi marcado como secret por acidente

A prova sintética garante que arquivos com conteúdo sensível seriam bloqueados

## Arquivos

Criado

`rag/sources/secret_detection.py`

Atualizado

`rag/sources/__init__.py`

Atualizado

`rag/runtime/index_request.py`

Criado

`tests/test_rag_secret_detection.py`

Criado

`docs/RAG_015_A_SECRETS.md`

## Critério de aceitação

RAG-015-A está concluído quando

- denylist por path continua funcionando
- secret em filename inocente é bloqueado
- provider tokens de alta confiança são detectados
- private key é detectada
- assignments sensíveis são detectados
- placeholders não viram falso positivo
- findings não retornam secret bruto
- sensitive_count fica auditável
- testes negativos passam
- suíte RAG passa
- git diff check passa

## Próximo passo

`RAG-015-B — Escopo`

Provar negativamente que projeto A não recebe resultados do projeto B quando scope explícito está ativo
