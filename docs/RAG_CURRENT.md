# CodeBridge — RAG e conhecimentos atuais

## Componentes

| Componente | Responsabilidade |
|---|---|
| `rag/sources/` | Identificação e classificação de fontes; exclusões de caminhos sensíveis e temporários |
| `rag/chunking/` | Fragmentação de conteúdo preservando informações de origem |
| `rag/models/` | Políticas/modelos de embeddings, ciclo de vida e fallback |
| `rag/index/` | Armazenamento lexical, vetorial e manifestos |
| `rag/runtime/` | Pesquisa persistente, status, prévia de indexação, controles de geração e validação |
| `author_mcp/rag_bridge.py` | Ponte das ferramentas MCP para o RAG |
| `app_rewrite/rag_panel.py` | Interface de arquivos, pesquisa e inclusão em prévia |

### Recuperação

- SQLite FTS5/BM25: busca textual/lexical.
- Qdrant local: vetores para recuperação semântica.
- Jina Embeddings: famílias separadas para documentos e código.
- Busca híbrida e resultados com referências a arquivo, linhas, metadados e hashes quando presentes no índice.
- A pesquisa retorna dados indexados; para código modificado desde a indexação, confirmar o arquivo atual no repositório.

### Geração observada

```text
state             READY
generation        v1_delta_1ae1d01ea84f4e
project           codebridge
document_count    211
text_entries      109
code_entries      102
chunk_count       8774
last_indexed_at   2026-10-09T11:17:53Z
```

O estado acima foi lido da instalação conectada em 24/10/2026. Dados operacionais variam; consultar `codebridge_rag_status` para o momento presente.

## Funções MCP utilizáveis

- `codebridge_rag_status`: inspecionar índice e modelos.
- `codebridge_search_context`: obter trechos relevantes para uma pergunta, com filtros por fonte/caminho/branch quando aplicáveis.
- `codebridge_get_context`: recuperar chunks autorizados.
- `codebridge_rag_index(...,execute=false)`: selecionar/validar candidatos **sem executar indexação**.

## Gestão de fontes pela interface

O painel oferece páginas **Meus arquivos**, **Pesquisar** e **Adicionar**. Há escolha de pasta e seleção de um ou vários arquivos para prévia; revisão de autorização exibida na interface é simulada. O botão de publicação/indexação efetiva permanece desabilitado. A instalação de um novo arquivo da interface pode exigir reinicialização do aplicativo para exibir o recurso.

### Limite de escrita

O código contém mecanismos de staging, validação e controle de gerações, mas a **gravação incremental e a publicação em produção de fontes novas não estão certificadas nem liberadas**. Não usar `execute=true` para contornar o gate.

Não há canal automático implícito de arquivo anexado ao ChatGPT para o filesystem Windows. Qualquer recebimento futuro exige transferência explícita, autorização de fonte, validação de conteúdo/escopo e comprovante.

## Integridade

- Índices persistidos contêm SQLite, Qdrant e manifesto de geração.
- Verificações de origem e hashes ajudam a identificar mudanças, mas não eliminam o risco de índice desatualizado.
- Publicação atômica, leitores presos à mesma geração, atualização, exclusão e rollback completo exigem certificação ponta a ponta.
- Precisão de recuperação não deve ser expressa em porcentagem sem avaliação reproduzível com respostas conhecidas.

## Segurança de fontes

O inventário aplica regras de rejeição a exemplos como ambientes virtuais, dependências, caches, binários, backups e nomes de arquivos de credenciais/chaves. A aprovação de uma pasta não equivale à aprovação irrestrita de todos os seus arquivos.

A documentação histórica não é a fonte de verdade para código executável. Utilizar estado real do servidor e arquivos atuais quando houver divergência.
