# Conhecimentos e busca RAG

## O que faz

O RAG do CodeBridge localiza trechos de arquivos e código de um projeto, disponibilizando contexto para análise. Ele **não é a fonte de verdade do repositório**: edições e verificações de atualidade devem consultar arquivos e Git.

## Recursos expostos

- `codebridge_rag_status()`: inspeciona índice, geração, projetos e modelos.
- `codebridge_search_context(query, project, top_k=10, ...)`: consulta um projeto, com filtros opcionais por tipo, caminho e branch.
- `codebridge_get_context(project, chunk_ids, ...)`: recupera chunks identificados pela busca e aplica regras de escopo/atualidade.
- `codebridge_rag_index(project_id, project_root, scope="BOTH", paths=None, execute=False)`: planeja fontes elegíveis, sem escrever quando `execute=false`.

## Aplicativo desktop

`app_rewrite/rag_panel.py::RagPanel` oferece páginas para listar conhecimentos, pesquisar e adicionar fontes. `browse` seleciona uma pasta; `browse_files` permite selecionar arquivos individuais ou múltiplos. `plan` apresenta prévia e `cancel_preview` invalida prévia pendente. `review_authorization` é revisão **simulada na interface**, não autorização de publicação persistida.

## Fonte e escopo

Inventários de documentos e código reconhecem formatos específicos. As políticas de exclusão rejeitam material sensível, cache, dependências, binários, temporários e caminhos potencialmente inseguros. Um arquivo anexado ao ChatGPT não aparece automaticamente no filesystem Windows: qualquer transferência futura precisa ser explícita e autorizada.

## Estado operacional

O índice RAG publicado pode estar disponível para consulta enquanto a escrita incremental sobre uma geração ativa continua bloqueada ou não certificada. A existência de rotinas de staging, fila ou verificação não significa que novas fontes estejam publicadas.

Para cada resultado, verificar origem, arquivo, linhas, hashes, branch e atualidade quando fornecidos. Se o índice estiver defasado, consultar o arquivo atual no projeto.

## Diagnóstico

Primeiro use `codebridge_rag_status` e confirme `READY` e geração; depois teste uma pesquisa conhecida. Erros de modelos, backend vetorial, locks, geração ausente e falta de fontes são problemas diferentes. A recuperação não deve ser feita sobrescrevendo a geração ativa manualmente.

Mais detalhes sobre mecanismos internos: [RAG_INTERNALS.md](RAG_INTERNALS.md). Dados persistentes: [STORAGE.md](STORAGE.md).