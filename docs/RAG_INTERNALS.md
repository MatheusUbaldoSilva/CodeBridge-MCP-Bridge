# Estrutura interna do RAG

## Pipeline

```text
Inventário de fontes -> validação de caminhos/segredos
       -> chunking de texto/código e proveniência
       -> embeddings sob demanda
       -> SQLite FTS5/BM25 + Qdrant local
       -> busca híbrida, fusão, deduplicação e reranking
       -> chunks e metadados autorizados
```

## Componentes e responsabilidades

| Código | Papel |
|---|---|
| `rag/sources/` | inventários, exclusões, Git, atualização e identidade da fonte |
| `rag/chunking/` | fragmentação e preservação de linhas/caminhos |
| `rag/models/` | inferência, modelos, memória, ciclo de vida e fallback |
| `rag/index/` | SQLite, Qdrant, manifesto, caches e esquema |
| `rag/retrieval/` | estratégias híbridas para documentos e código |
| `rag/ranking/` | fusão e reordenação de candidatos |
| `rag/runtime/` | consultas persistentes, gerações, integridade, fila e publicação controlada |
| `author_mcp/rag_bridge.py` | ligação das chamadas MCP com a implementação local |

## Modelos e busca

São usadas famílias Jina para embeddings de texto e código. O gerenciador pode carregá-las sob demanda, respeitando recursos locais e regras de fallback. O mecanismo lexical usa SQLite FTS5/BM25; os vetores semânticos são mantidos no Qdrant local.

Funções implementadas incluem `reciprocal_rank_fusion` (`rag/ranking/rrf.py`), `deduplicate_ranked_results` (`dedup.py`), `select_diverse_passages` (`passage_diversity.py`), `rerank_multi_passage` (`multi_passage_reranker.py`) e `cross_encoder_rerank` (`local_cross_encoder.py`). O cross-encoder aceita apenas endpoint local validado e reordena candidatos; não cria fontes. Nem todas as etapas são necessariamente usadas em toda consulta.

## Gerações e segurança de publicação

`generation_pointer.py::resolve_generation` valida o ponteiro `active-generation.json`, identificador e diretório; código de sessão/lease/lock protege leitores e transições. Existem journal, backup e recuperação de gerações, além de staging de SQLite, Qdrant e manifesto.

`production_publish.py::publish_staged_index` destina-se à publicação inicial e rejeita produção já existente. Por isso não pode ser usado como atalho para alterar uma geração publicada. O caminho incremental depende de admissão de fontes, revisão, consistência dos três stores, transição, recuperação e gates operacionais.

## Proveniência

IDs determinísticos de documento/chunk, hash de fonte e metadados Git ajudam a rastrear resultados. A presença de SHA ou commit não garante que o arquivo em disco permaneça igual após a indexação.

## Limite de prontidão

O código contém mecanismos de fila e worker offline; não considerar escrita incremental ou atualização em produção certificadas apenas pela existência desses módulos. Para verificações e recuperação, consultar [RECOVERY.md](RECOVERY.md).