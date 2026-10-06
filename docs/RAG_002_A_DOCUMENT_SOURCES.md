# RAG-002-A — Inventário de fontes documentais

Data: 2026-10-06  
Projeto: CodeBridge 2.0 — MCP Bridge  
Branch: `rag-002-source-inventory`

## Objetivo

Mapear as fontes documentais autorizáveis previstas no handoff sem iniciar chunking indexação embedding ou carregamento de modelos

Categorias previstas

- README
- documentação
- handoffs
- roadmaps
- patch notes
- auditorias

## Regra de classificação

A classificação determinística deste subpasso está em

`rag/sources/document_inventory.py`

Regras congeladas em RAG-002-A

- arquivos README são documentação em qualquer diretório
- nomes contendo HANDOFF são handoffs
- nomes contendo ROADMAP são roadmaps
- nomes compatíveis com PATCH NOTE são patch notes
- nomes compatíveis com AUDIT ou AUDITORIA são auditorias
- Markdown RST e AsciiDoc são documentação textual
- TXT genérico só entra automaticamente quando estiver em `docs/`
- `requirements.txt` não é documentação e fica fora deste inventário
- esta fase somente classifica paths
- esta fase não lê conteúdo para indexar
- esta fase não cria chunks
- esta fase não cria índice
- esta fase não carrega Jina

## Snapshot atual do repositório

Inventário feito sobre o HEAD que encerrou RAG-001

### README

| path | bytes | blob SHA |
| --- | ---: | --- |
| `README.md` | 3016 | `ad07e2ce41b7f22df0e090ca5426639975774445` |
| `manual_tests/README.md` | 664 | `1b31a11cd3af99f26dedc8b2376ea6c503f1a4fb` |

### Documentação

| path | bytes | blob SHA |
| --- | ---: | --- |
| `author_mcp/PROTOCOL.md` | 1720 | `d030d56281d6970852814d179266b189d60e4698` |
| `docs/ARCHITECTURE.md` | 2899 | `a7b45881130a4068d96edbd87d19e084a3eb9b9a` |
| `docs/INSTALLER.md` | 6820 | `0e3983290552d1a9724ec452d3a55ee83b3b39c2` |
| `docs/RAG_001_CLOSEOUT.md` | 4240 | `342c2f779144096a6789ebec106487b09209c0b9` |
| `docs/RAG_CONTRACT.md` | 5863 | `14f32cee172db1e0f51cd758af50510890207673` |
| `docs/RAG_MODULE_LAYOUT.md` | 6396 | `ae248efda87507d5e4545961728cf2557319fb23` |

### Handoffs

| path | bytes | blob SHA |
| --- | ---: | --- |
| `docs/HANDOFF_RAG_JINA_CODEBRIDGE_2_0_2026-10-06.md` | 19191 | `3b8678d19671d65f25e5eb53ee1aad31b9cfddab` |

### Roadmaps

| path | bytes | blob SHA |
| --- | ---: | --- |
| `docs/ROADMAP.md` | 1504 | `5029633823b6626d1c8681d77779e885b4712367` |

### Patch notes

Nenhum arquivo de patch notes foi encontrado no branch auditado

Isso significa apenas que não existe patch note versionado neste repositório nesse snapshot

Não significa que patch notes externos não existam

### Auditorias

Nenhum arquivo de auditoria foi encontrado no branch auditado

Isso significa apenas que não existe auditoria versionada neste repositório nesse snapshot

Pastas externas de auditoria não são assumidas nem indexadas automaticamente

Elas só poderão entrar depois de uma raiz autorizada ser definida

## Arquivos textuais encontrados mas fora da categoria documental

| path | motivo |
| --- | --- |
| `requirements.txt` | manifest de dependências |
| `author_mcp/requirements.txt` | manifest de dependências |

Esses arquivos podem ser avaliados no inventário de código/configuração do RAG-002-B

## Totais do snapshot

```text
fontes documentais elegíveis = 10

README        = 2
DOCUMENTATION = 6
HANDOFF       = 1
ROADMAP       = 1
PATCH_NOTE    = 0
AUDIT         = 0
```

## Fora do escopo deste subpasso

Ainda não foram definidos

- extensões de código permitidas
- metadados Git a indexar
- campos de execução do ledger
- denylist global
- roots externas autorizadas
- chunking
- SQLite
- embeddings
- modelos

Esses itens pertencem aos próximos subpassos do RAG-002 e marcos posteriores

## Critério de aceitação do RAG-002-A

RAG-002-A está concluído quando

- as seis classes documentais do handoff estão mapeadas
- o inventário atual do repositório está documentado
- manifests de dependência não são confundidos com documentação
- ausência atual de patch notes e auditorias está explícita
- nenhuma indexação ou inferência foi iniciada
