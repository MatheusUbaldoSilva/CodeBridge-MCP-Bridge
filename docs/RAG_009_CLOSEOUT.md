# RAG-009 — Closeout do índice vetorial

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-009-vector-index`

## Estado

`RAG-009 ✅ FECHADO`

O critério do handoff foi cumprido

O CodeBridge agora possui backend vetorial local selecionado coleções separadas para texto e código namespaces de projeto e identidade determinística com prova real de reindexação idempotente

## Base

RAG-009 parte do fechamento do RAG-008

`d16be9b docs(rag-008): close model manager milestone`

## RAG-009-A — Escolha do armazenamento

Commit

`86f131a feat(rag-009-a): select persistent Qdrant local backend`

Candidatos comparados

- Qdrant Local
- sqlite-vec
- LanceDB Local

Critérios do handoff

- estabilidade
- tamanho
- performance
- instalação
- backup
- portabilidade

Decisão

`QDRANT_LOCAL`

Versão congelada

`qdrant-client==1.19.1`

Modo

```text
persisted local mode
external server = false
auto install = false
scope = LOCAL_SINGLE_USER
```

Nenhum servidor Qdrant externo é exigido no caminho inicial

## RAG-009-B — Coleções separadas

Commit

`7e0b052 feat(rag-009-b): add separate text and code collections`

Coleções

### text

```text
dimension=1024
distance=Cosine
```

### code

```text
dimension=1536
distance=Cosine
```

Provas reais

- storage Qdrant Local criado em diretório temporário
- coleções text e code criadas
- close e reopen preservaram as coleções
- ensure repetido não duplicou coleções
- contrato com dimensão incompatível foi rejeitado
- adapter mantém import lazy
- qdrant-client foi adicionado ao requirements.txt

Compatibilidade adicional

Foi encontrado e isolado um ResourceWarning do probe SQLite do qdrant-client 1.19.1 no Python 3.13

O adapter do CodeBridge passou a executar o mesmo probe com fechamento explícito da conexão

Validação

`python -W error::ResourceWarning`

passou sem warning

Nenhum arquivo do pacote externo instalado foi modificado

## RAG-009-C — Namespaces de projeto

Commit

`087724e feat(rag-009-c): add project vector namespaces`

Campo de payload

`project_namespace`

Exemplos congelados pelo handoff

```text
codebridge
new-world-pvp
drones
outros
```

Contrato

- lowercase ASCII
- letras dígitos e hífen
- 1 a 64 caracteres
- sem espaço
- sem hífen no começo ou final
- sem hífens consecutivos

A camada não faz slug automático para evitar colisão silenciosa de IDs

Prova real

Dentro da coleção text foram indexados pontos de

`codebridge`

e

`drones`

O filtro de namespace retornou somente o projeto solicitado

A mesma prova foi repetida na coleção code com

`new-world-pvp`

e

`outros`

## RAG-009-D — IDs determinísticos

Commit

`6686650 feat(rag-009-d): add deterministic vector identities`

Identidade de documento

```text
doc:<sha256>
```

derivada de

- project namespace
- source_type
- path relativo canônico

Identidade de chunk

```text
chunk:<sha256>
```

derivada de

- document_id
- ordinal
- SHA-256 do conteúdo

Point ID vetorial

UUID v5 determinístico derivado de

- project namespace
- coleção
- chunk_id

Consequências

- mesmo chunk mesma coleção mesmo projeto → mesmo point ID
- outro projeto → outro point ID
- outra coleção → outro point ID

## Reindexação idempotente

Prova real com Qdrant Local

### text

O mesmo chunk foi indexado duas vezes

A segunda indexação alterou um campo de payload

Resultado

```text
point_id primeira == point_id segunda
quantidade final de pontos = 1
payload final contém revisão nova
```

### code

O mesmo chunk foi indexado três vezes

Resultado

```text
quantidade final de pontos = 1
```

Portanto o requisito do handoff foi provado

`Mesmo chunk não pode criar duplicatas a cada indexação`

## Contratos preservados

O helper histórico de provenance continua aceitando chunk_ids fornecidos pelo chamador

A política oficial determinística está congelada em

`rag.index.vector_ids`

Isso mantém compatibilidade dos contratos anteriores sem reescrever o chunking já fechado

## Dependência instalada

Ambiente de desenvolvimento

`qdrant-client==1.19.1`

requirements

`qdrant-client==1.19.1`

O RAG não inicia servidor externo

Qdrant Local roda embutido no processo quando explicitamente aberto

## Testes

Suíte RAG antes do closeout

```text
Ran 457 tests
OK
```

Auditorias executadas em cada subfase

```text
git diff --check
OK
```

```text
git diff --cached --check
OK
```

Branch após RAG-009-D

```text
origin/rag-009-vector-index...HEAD
0 0
```

## Arquitetura consolidada

```text
chunk
↓
project namespace
↓
coleção
├── text 1024D cosine
└── code 1536D cosine
↓
document_id determinístico
↓
chunk_id determinístico
↓
UUID v5 determinístico do ponto
↓
Qdrant Local persistente
↓
upsert
↓
reindex do mesmo chunk atualiza o mesmo ponto
```

## Fronteiras preservadas

Não pertencem ao RAG-009

### RAG-010

Busca híbrida

- FTS5 + vetor textual
- FTS5 + vetor de código
- consulta HYBRID
- fusão determinística
- deduplicação

### RAG-011

Metadados Git e staleness

### RAG-012

Indexação incremental

- arquivo inalterado não reindexa
- arquivo alterado reindexa somente o necessário
- arquivo removido remove chunks órfãos
- mudança de modelo invalida somente o índice correspondente

Esses marcos não foram antecipados

## Critério de fechamento

RAG-009 pode ser marcado fechado porque

- backend vetorial foi comparado e selecionado
- versão foi congelada
- storage local persistente foi validado
- coleções text e code são separadas
- namespaces de projeto foram implementados
- isolamento por namespace foi provado
- IDs de documento chunk e ponto são determinísticos
- reindexação do mesmo chunk foi provada como idempotente
- 457 testes RAG passaram
- diff check passou
- commits A B C D existem
- branch está sincronizada com origin antes do closeout

## Próximo marco

`RAG-010 — Busca híbrida`

Primeiro passo oficial

`RAG-010-A — FTS5 + vetor textual`

Objetivo imediato

combinar resultados lexicais existentes com recuperação vetorial textual sem ainda antecipar a fusão final de todos os modos
