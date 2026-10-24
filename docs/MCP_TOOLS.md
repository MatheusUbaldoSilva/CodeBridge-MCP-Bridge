# Ferramentas MCP

Catálogo declarado no código de `author_mcp/mcp_server.py`, com duas ferramentas adicionais de checkpoint registradas por `author_mcp/development_checkpoint_tools.py`. A conexão ativa pode expor apenas um subconjunto.

## Estado e inspeção

| Ferramenta | Argumentos | Função |
|---|---|---|
| `codebridge_status` | nenhum | handshake, versão, disponibilidade e estados |
| `codebridge_capabilities` | nenhum | alvos, limites e recursos |
| `codebridge_read_batch` | `operations` | lote de leituras validadas |

Operações permitidas em `codebridge_read_batch`: `GIT_STATUS`, `GIT_HEAD`, `GIT_BRANCH`, `VERSION`, `FILE_STAT`, `SHA256`. Um item recebe `kind`, `id` opcional e `path` para todos exceto `VERSION`.

## Terminais

| Ferramenta | Assinatura |
|---|---|
| `codebridge_prepare` | `(target, command)` |
| `codebridge_execute_prepared` | `(prepared_request_id)` |
| `codebridge_discard` | `(request_id=None)` |
| `codebridge_exec` | `(target, command, wait_timeout_ms=1500, output_mode="NORMAL")` |
| `codebridge_wait` | `(execution_id, cursor=0, wait_timeout_ms=15000, max_chars=32768, output_mode="NORMAL")` |
| `codebridge_stop` | `(execution_id=None)` |

Alvos do executor: `POWERSHELL5.1`, `CMD` e `SSH` quando conectado. Modos de saída: `NORMAL`, `COMPACT`, `RAW`. Uma resposta `RUNNING` exige esperar pelo `execution_id`, nunca reexecutar o mesmo comando inadvertidamente.

## RAG

| Ferramenta | Assinatura |
|---|---|
| `codebridge_rag_status` | nenhum |
| `codebridge_rag_generation_probe` | nenhum |
| `codebridge_rag_integrity` | nenhum |
| `codebridge_rag_queue_bootstrap` | `(execute=False, operator_approved=False, confirmation=None, expected_generation=None)` |
| `codebridge_rag_index` | `(project_id, project_root, scope="BOTH", paths=None, execute=False)` |
| `codebridge_search_context` | `(query, project, source_types=None, top_k=10, path_filter=None, branch=None)` |
| `codebridge_get_context` | `(project, chunk_ids, include_document_content=False, project_root=None, allow_stale=False)` |

`codebridge_rag_index` em modo padrão apenas planeja fontes. A escrita incremental no índice ativo continua sujeita a gates e não pode ser presumida liberada.

## Checkpoints

- `codebridge_dev_checkpoint_save(summary, next_step, completed=None, pending=None)`: grava resumo da sessão autorizada.
- `codebridge_dev_checkpoint_latest(session_id=None)`: consulta o último resumo disponível.

Checkpoints não fazem backup de índice nem commit Git.

## Exemplo de chamada

```json
{"target":"POWERSHELL5.1","command":"Get-Date","wait_timeout_ms":1500,"output_mode":"NORMAL"}
```

Para pesquisas, forneça `project`, `query` e opcionalmente `top_k` a `codebridge_search_context`. Para obter chunks, use os `chunk_ids` retornados pela pesquisa em `codebridge_get_context`.

Resultados informam campos de estado, erro, execução e saída; consulte `operation_ok`, `error_type`, `execution_id` e `exit_code` quando disponíveis. As assinaturas exatas válidas são sempre as anunciadas pelo servidor MCP conectado.