# Ferramentas MCP — contratos da branch atual

Catálogo declarado em `author_mcp/mcp_server.py`. A assinatura do servidor é a fonte de verdade; uma ferramenta declarada pode não estar exposta pela conexão ChatGPT da instalação corrente. As ferramentas de terminal operam com as permissões da sessão real do computador.

## Estado e descoberta

| Ferramenta | Parâmetros | Resultado |
|---|---|---|
| `codebridge_status` | Nenhum | Protocolo, handshake, versão, disponibilidade de terminais, estado do executor |
| `codebridge_capabilities` | Nenhum | `targets`, `features`, `limits`, ferramentas preferidas e migração |
| `codebridge_read_batch` | **`operations: list[dict]`** | Executa lote restrito de consultas de leitura |

### `codebridge_read_batch` — contrato exato

Cada elemento de `operations` aceita somente as chaves `id` (opcional), `kind` e `path`. Tipos permitidos: `GIT_STATUS`, `GIT_HEAD`, `GIT_BRANCH`, `VERSION`, `FILE_STAT` e `SHA256`. `VERSION` **não aceita `path`**; todos os outros tipos exigem `path`.

```json
{
  "operations": [
    {"id": "git", "kind": "GIT_STATUS", "path": "C:\\Users\\Matheus\\CodeBridge-MCP-Bridge"},
    {"id": "app", "kind": "VERSION"}
  ]
}
```

Máximo observado na versão auditada: 32 operações e 8 workers. Campos desconhecidos rejeitam a validação. O nome `requests` **não é** o parâmetro desta ferramenta.

## Executor e controle

| Ferramenta | Assinatura essencial | Função |
|---|---|---|
| `codebridge_prepare` | `(target: str, command: str)` | Prepara o comando no terminal sem enviar Enter |
| `codebridge_execute_prepared` | `(prepared_request_id: str)` | Envia Enter do comando preparado |
| `codebridge_discard` | `(request_id: str | None = None)` | Descarta preparação sem executar |
| `codebridge_exec` | `(target, command, wait_timeout_ms=1500, output_mode="NORMAL")` | Inicia execução pelo executor V2 |
| `codebridge_wait` | `(execution_id, cursor=0, wait_timeout_ms=15000, max_chars=32768, output_mode="NORMAL")` | Consulta estado e saída incremental sem reenviar Enter |
| `codebridge_stop` | `(execution_id: str | None = None)` | Interrompe execução especificada ou fluxo ativo/preparado |

Alvos suportados pela instalação observada: `POWERSHELL5.1`, `CMD` e `SSH`. `SSH` depende de a sessão estar online. `codebridge_capabilities` informa limites reais.

Exemplo de `codebridge_exec`:

```json
{"target":"POWERSHELL5.1","command":"Get-Date","wait_timeout_ms":1500,"output_mode":"NORMAL"}
```

Para resposta `RUNNING`, continue por `codebridge_wait` com o **mesmo `execution_id`**:

```json
{"execution_id":"<execution_id retornado>","cursor":0,"wait_timeout_ms":15000,"output_mode":"RAW"}
```

`NORMAL` pode compactar saídas extensas automaticamente; `COMPACT` solicita resumo, `RAW` preserva a recuperação. Os campos `stdout`/`stderr` expostos devem ser interpretados conforme o contrato de `stream_mode` e `streams_separated` do retorno: não presumir streams independentes em toda sessão.

## Conhecimento e RAG

| Ferramenta | Assinatura/parâmetros | Função |
|---|---|---|
| `codebridge_rag_status` | `()` | Estado da geração pública, manifesto, SQLite, Qdrant, projetos e modelos |
| `codebridge_rag_index` | `(project_id, project_root, scope="BOTH", paths=None, execute=False)` | Planejamento das fontes e execução condicionada a gates |
| `codebridge_search_context` | `(query, project, source_types=None, top_k=10, path_filter=None, branch=None)` | Pesquisa restrita ao projeto com filtros e proveniência |
| `codebridge_get_context` | `(project, chunk_ids, include_document_content=False, project_root=None, allow_stale=False)` | Recupera chunks identificados e autorizados |
| `codebridge_rag_generation_probe` | `()` | Sonda a geração; método declarado, não necessariamente exposto |
| `codebridge_rag_integrity` | `()` | Verificações diagnósticas de integridade; pode não estar exposto |
| `codebridge_rag_queue_bootstrap` | `(execute=False, operator_approved=False, confirmation=None, expected_generation=None)` | Verifica/inicia mecanismo restrito de bootstrap da fila; não equivale a publicação |

### Exemplos seguros

`codebridge_search_context`:

```json
{"project":"codebridge","query":"Onde fica o ledger de execução?","top_k":5}
```

`codebridge_get_context` (utilize IDs **retornados pela busca**, não paths arbitrários):

```json
{"project":"codebridge","chunk_ids":["<id de chunk válido>"],"include_document_content":false,"allow_stale":false}
```

`codebridge_rag_index` (somente prévia):

```json
{"project_id":"codebridge","project_root":"C:\\Users\\Matheus\\CodeBridge-MCP-Bridge","scope":"BOTH","paths":["README.md"],"execute":false}
```

A publicação incremental no índice público está **bloqueada ou não certificada**. `execute=true` não é um atalho de autorização. A ferramenta de bootstrap possui um contrato próprio de aprovação e gates; sua presença no servidor não prova que foi habilitada na conexão atual.

## Nomes legados

A família `codebridge_v2_start/status/output/result/stop` e nomes `codebridge_start`, `codebridge_execution_status` e `codebridge_terminal` aparecem em políticas de compatibilidade. Novos clientes devem preferir `codebridge_exec`, `codebridge_wait`, `codebridge_stop`, `codebridge_prepare` e `codebridge_execute_prepared`.

## Fonte e observabilidade

- Assinaturas: `author_mcp/mcp_server.py`.
- Esquema do lote: `app_rewrite/read_only_batch.py::_validate_operations`.
- Estados persistentes: `app_rewrite/execution_ledger.py`.
- Busca e contexto: `author_mcp/rag_bridge.py`.
- Disponibilidade efetiva: chamada real `codebridge_status` e ferramentas anunciadas pela conexão.

Leia também [EXECUTION_RUNTIME_CURRENT.md](EXECUTION_RUNTIME_CURRENT.md), [SECURITY_AND_PERSISTENCE_CURRENT.md](SECURITY_AND_PERSISTENCE_CURRENT.md) e [RAG_INTERNALS_CURRENT.md](RAG_INTERNALS_CURRENT.md).
