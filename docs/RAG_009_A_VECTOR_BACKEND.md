# RAG-009-A — Escolha do armazenamento vetorial

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-009-vector-index`

## Objetivo

Comparar opções locais antes de congelar o backend vetorial

Critérios exigidos pelo handoff

- estabilidade
- tamanho
- performance
- instalação
- backup
- portabilidade

## Candidatos avaliados

Foram avaliados

- Qdrant Local persistido em disco pelo cliente Python
- sqlite-vec
- LanceDB OSS local

Nenhum backend foi instalado no runtime principal durante esta fase

Nenhum serviço vetorial foi iniciado

## Evidência externa consultada

Qdrant

A documentação oficial do cliente descreve local mode sem servidor com persistência por `path`

Também alerta que local mode é mais indicado para testes depuração ou quantidade pequena de vetores

O deployment completo local por servidor normalmente usa Docker

sqlite-vec

A documentação upstream continua marcando o projeto como pre-v1 e avisa que mudanças incompatíveis podem ocorrer

LanceDB

A documentação oficial apresenta o modo OSS local como embedded e persistido em diretório

A arquitetura é forte para vetores locais mas o artefato Windows observado é significativamente maior

## Versões observadas no ambiente em 2026-10-07

Consulta feita com

`python -m pip index versions`

Resultados mais recentes observados

```text
qdrant-client 1.19.1
sqlite-vec 0.1.9
lancedb 0.40.0
```

## Medição de tamanho

Foi usado

`pip download --no-deps`

em diretório temporário

Nada foi instalado

Os arquivos baixados foram removidos depois da medição

```text
qdrant_client-1.19.1-py3-none-any.whl
406533 bytes

sqlite_vec-0.1.9-py3-none-win_amd64.whl
292804 bytes

lancedb-0.40.0-cp310-abi3-win_amd64.whl
83389723 bytes
```

Importante

Esses números medem somente o wheel principal

Dependências transitivas não estão incluídas

Portanto são evidência de footprint inicial e não tamanho final instalado

## Comparação

Escala

1 pior

5 melhor

| Critério | Qdrant Local | sqlite-vec | LanceDB Local |
| --- | ---: | ---: | ---: |
| Estabilidade | 4 | 2 | 4 |
| Tamanho | 4 | 5 | 1 |
| Performance | 3 | 3 | 5 |
| Instalação | 5 | 5 | 3 |
| Backup | 3 | 5 | 4 |
| Portabilidade | 4 | 5 | 5 |

Os scores são decisão arquitetural desta fase

Não são benchmark de throughput

Performance real do índice será medida depois da integração

## Qdrant Local

Pontos favoráveis

- modo local oficial dentro do processo Python
- persistência em disco por path
- não exige servidor para o escopo inicial
- API mantém caminho claro de migração futura para Qdrant server
- pacote principal observado é pequeno comparado ao LanceDB
- collections e payloads atendem o roadmap posterior

Limitações registradas

- documentação posiciona local mode para datasets pequenos testes ou depuração
- backup por cópia de diretório local ainda deverá ser validado com o cliente fechado
- performance não foi benchmarkada nesta fase
- não será usado para escala distribuída

## sqlite-vec

Pontos favoráveis

- footprint muito pequeno
- alinhamento natural com SQLite já usado pelo FTS5
- excelente portabilidade
- backup simples como armazenamento SQLite

Motivo principal da rejeição

O upstream ainda declara o projeto pre-v1 com expectativa de breaking changes

Isso conflita diretamente com o critério de estabilidade para um contrato que será congelado no CodeBridge 2.0

Pode ser reavaliado no futuro quando a API atingir estabilidade adequada

## LanceDB Local

Pontos favoráveis

- embedded
- persistência local
- arquitetura orientada a datasets e vetores
- forte portabilidade
- bom caminho de performance para volumes maiores

Motivo principal de não seleção

O wheel Windows observado tem

`83389723 bytes`

aproximadamente 83.4 MB antes das dependências

Para o CodeBridge desktop essa fase prioriza uma superfície inicial menor

LanceDB continua uma alternativa válida caso o benchmark futuro mostre que Qdrant Local não atende

## Decisão

Backend selecionado

`QDRANT_LOCAL`

Pacote congelado para a próxima fase

`qdrant-client==1.19.1`

Modo

```text
persisted local mode
external server = false
auto install = false
scope = LOCAL_SINGLE_USER
```

Nenhum Docker será exigido para o caminho inicial

Nenhum servidor Qdrant será iniciado no RAG-009-A

## Política de instalação

Download ou instalação automática continuam proibidos

RAG-009-A somente congela a decisão

A instalação controlada e a primeira integração devem ocorrer explicitamente na fase que realmente precisar do cliente

## Arquivos

Criado

`rag/index/vector_backend_policy.py`

Atualizado

`rag/index/__init__.py`

Criado

`tests/test_rag_vector_backend_policy.py`

Criado

`docs/RAG_009_A_VECTOR_BACKEND.md`

## Referências consultadas

Qdrant documentation

Local mode with on-disk persistence

Qdrant local deployment and installation documentation

sqlite-vec upstream documentation

pre-v1 stability warning

LanceDB official local embedded documentation

## Fronteiras

RAG-009-A não cria collections

Não instala qdrant-client

Não abre banco vetorial

Não cria namespace

Não define IDs de pontos

Não faz reindexação

Esses pontos pertencem a RAG-009-B C D

## Critério de aceitação

RAG-009-A está concluído quando

- candidatos foram comparados pelos seis critérios do handoff
- tamanho foi medido de forma reproduzível
- estabilidade foi considerada
- uma opção foi selecionada
- pacote e versão foram congelados
- auto install permanece desligado
- import da policy não carrega qdrant-client
- testes específicos passam
- suíte RAG passa
- git diff check passa
