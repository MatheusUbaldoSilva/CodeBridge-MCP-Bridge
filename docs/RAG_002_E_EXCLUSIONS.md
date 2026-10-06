# RAG-002-E — Denylist inicial de fontes

Data: 2026-10-06  
Projeto: CodeBridge 2.0 — MCP Bridge  
Branch: `rag-002-source-inventory`

## Objetivo

Criar a política inicial de exclusão exigida pelo handoff

A denylist é aplicada antes das allowlists documentais e de código

Regra central

```text
denylist
   ↓
se negado encerra avaliação
   ↓
allowlist documental ou técnica
```

Isso impede que um arquivo com extensão permitida entre no RAG apenas porque termina em `.py` `.js` `.json` ou `.md`

## Exclusões obrigatórias do handoff

Cobertas por esta política

- `.git/objects`
- `.venv`
- `node_modules`
- `build`
- `dist`
- caches
- binários
- backups
- temporários
- credenciais
- `.env`
- chaves privadas
- tokens

## Diretórios negados

### Git interno pesado

```text
.git/objects/
```

Objetos Git não são fontes diretas do RAG

Informação Git deve entrar pelo contrato do RAG-002-C

### Ambientes virtuais

```text
.venv/
venv/
```

### Dependências vendorizadas

```text
node_modules/
```

### Build e distribuição

```text
build/
dist/
```

### Caches

```text
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.cache/
cache/
caches/
```

### Backups

```text
backup/
backups/
.backup/
.backups/
```

### Temporários

```text
tmp/
temp/
.tmp/
.temp/
```

## Binários e artefatos não textuais

A política bloqueia extensões como

```text
.exe .dll .so .dylib .bin
.o .obj .a .lib .class .jar
.pyc .pyo .wasm
.png .jpg .jpeg .gif .bmp .webp .ico
.mp3 .wav .ogg .flac
.mp4 .avi .mov .mkv
.zip .7z .rar .tar .gz .bz2 .xz
```

O objetivo do RAG é indexar contexto textual autorizado

Binários podem continuar existindo normalmente no projeto sem entrar no índice

## Credenciais e secrets

### Arquivos de ambiente

```text
.env
.env.local
.env.production
.env.*
```

### Credenciais

Exemplos bloqueados

```text
credentials.json
credential.json
secrets.json
client_secret.json
```

### Chaves privadas

Exemplos bloqueados

```text
id_rsa
id_dsa
id_ecdsa
id_ed25519
*.pem
*.key
*.p12
*.pfx
*.jks
*.keystore
*.kdbx
```

### Tokens e chaves de API

Nomes contendo marcadores explícitos como

```text
token
api_token
access_token
refresh_token
api_key
access_key
```

são negados pelo path

A filtragem por conteúdo ainda será uma camada adicional antes de indexação real

## Backups por extensão

```text
*.bak
*.backup
*.old
*.orig
*.save
*~
```

## Temporários por extensão

```text
*.tmp
*.temp
*.swp
*.swo
```

## Path traversal

Também é negado qualquer path contendo

```text
..
```

como componente

Isso evita que uma futura root autorizada seja contornada por path traversal

## Snapshot real do repositório

Na auditoria imediatamente anterior ao RAG-002-E foram encontrados 147 blobs

Candidatos reais já cobertos pela denylist

```text
installer/dist/CodeBridge-Setup.exe
installer/dist/CodeBridge-Setup.sha256
```

Os dois são negados por estarem em `dist/`

O checksum `.sha256` não precisa ser tratado como binário globalmente porque a regra de diretório já o bloqueia no artefato de distribuição

## Interação com as allowlists

Exemplos importantes

```text
.venv/tool.py
node_modules/app.js
dist/config.json
backup/script.ps1
config/api_token.json
```

Todos têm extensões que poderiam ser reconhecidas pela allowlist técnica

Mesmo assim ficam negados

Da mesma forma

```text
backups/README.md
tmp/ROADMAP.md
node_modules/README.md
```

seriam documentos válidos pela extensão ou nome mas a denylist vence

## Implementação

Criado

`rag/sources/exclusion_policy.py`

Contrato público

```text
DenyReason
classify_denied_path
is_denied_path
```

A função é pura

Ela não lê filesystem não executa comandos não abre banco não carrega modelo e não cria índice

## Testes

Criado

`tests/test_rag_exclusion_policy.py`

Coberturas principais

- diretórios negados
- binários
- backups
- temporários
- credenciais
- env files
- chaves privadas
- tokens
- path traversal
- paths Windows
- denylist vencendo allowlist de código
- denylist vencendo allowlist documental
- fontes legítimas permanecendo permitidas

## Invariantes

- denylist sempre precede allowlist
- secrets explícitos por path nunca entram
- ambiente virtual nunca entra
- dependências vendorizadas nunca entram
- build e dist nunca entram
- backups e temporários nunca entram
- binários não entram
- path traversal é bloqueado
- nenhuma indexação foi iniciada
- nenhum embedding foi gerado
- nenhum modelo foi carregado
- executor não foi alterado

## Critério de aceitação do RAG-002-E

RAG-002-E está concluído quando

- todas as exclusões do handoff possuem regra explícita
- denylist vence allowlists em testes
- fontes legítimas do CodeBridge não são bloqueadas
- artefatos reais em dist são detectados
- testes negativos cobrem credenciais secrets e tokens
- nenhuma fase posterior foi antecipada
