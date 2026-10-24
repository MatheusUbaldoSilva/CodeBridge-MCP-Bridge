# Segurança e persistência — estado atual

**Escopo:** mecanismos implementados na branch `rag-017-optimized-inference-after-candidate`. As afirmações referenciam módulos e funções do código; não constituem auditoria criptográfica independente ou certificação de produção.

## Credenciais e configurações

| Implementação | Responsabilidade | Observações |
|---|---|---|
| `app_rewrite/config_store.py::ConfigStore` | Ler/gravar configuração local; host/porta SSH, autoexecução, som e configuração da empresa | Escrita JSON via arquivo temporário e substituição; configuração não é um cofre de segredos |
| `app_rewrite/credential_store.py::WindowsCredentialStore` | Salvar, carregar, verificar e excluir credenciais SSH | Usa Windows Credential Manager e tipo `CRED_TYPE_GENERIC`; target padrão `CodeBridge-MCP-Bridge:SSH` |
| `app_rewrite/dpapi_secret_store.py::DPAPISecretStore` | Proteger segredo da API usada pelo túnel | Usa `CryptProtectData`/`CryptUnprotectData`; armazenamento de blob criptografado em arquivo; disponível somente no Windows |
| `app_rewrite/secure_tunnel_manager.py::SecureTunnelManager` | Preparar configuração, iniciar/parar e consultar túnel seguro | Usa configuração da empresa, chave de runtime e verificações de processo/health |

O `DPAPISecretStore.save` rejeita segredo vazio. `WindowsCredentialStore.save` exige login e senha informados. Não assumir que qualquer configuração JSON esteja criptografada: cada campo deve ser classificado de acordo com o módulo que o armazena.

**Regra de operação:** nunca exibir senhas, tokens, API keys, headers de autenticação ou conteúdo de blobs de credencial em resultados MCP, documentação ou commits.

## Canais e identidade de processos

- `app_rewrite/single_instance.py::SingleInstance`: exclusividade de instância por mutex local Windows (`Local\CodeBridge.MCP.Bridge.v2`).
- `app_rewrite/ipc_named_pipe.py`: transporte Windows Named Pipe com framing de 4 bytes, limite `MAX_MESSAGE_BYTES = 4 * 1024 * 1024`, validação e ACL construída a partir do SID do usuário atual.
- `app_rewrite/windows_control_channel.py::WindowsControlChannel`: inicialização, estado, espera de prontidão, operação e encerramento do canal de controle.
- `app_rewrite/author_mcp_manager.py::AuthorMCPManager`: supervisão dos processos do servidor/adapter MCP, com checagem de instâncias herdadas e encerramento controlado.
- `app_rewrite/secure_tunnel_manager.py`: ciclo de vida do processo de túnel e verificação de instância/listener.

Um Named Pipe local não transforma comandos em operações somente leitura; a autorização final continua vinculada ao runtime, ao protocolo e às permissões efetivas do usuário/shell.

## Estados persistentes de execução

| Implementação | Estruturas/funções existentes |
|---|---|
| `app_rewrite/execution_ledger.py::ExecutionLedger` | `create`, `transition`, `append_output`, `sync_output`, `read_output`, `list_by_state`, `interrupt_incomplete_from_other_runtime` |
| `app_rewrite/job_store.py::JobStore` | `create`, `mark_visible`, `approve`, `claim_next`, `mark_prepared`, `mark_running`, `finish`, `counts`, `prune_terminal_jobs` |
| `app_rewrite/external_prepare_store.py::ExternalPrepareStore` | Persistência de pedidos de preparação externos |
| `app_rewrite/external_execute_store.py::ExternalExecuteStore` | Persistência/identidade de pedidos de execução externos |

**Estados do ledger:** `CREATED`, `RUNNING`, `FINISHED`, `FAILED`, `CANCELLED` e `INTERRUPTED`. Transições documentadas no código: `CREATED` → `RUNNING/FAILED/CANCELLED/INTERRUPTED`; `RUNNING` → `FINISHED/FAILED/CANCELLED/INTERRUPTED`. Estados terminais não retornam para `RUNNING`.

O ledger utiliza SQLite e transações, com rollback de transação na ocorrência de exceção. O `execution_id` identifica uma execução; `request_id` identifica a solicitação, e não deve ser reutilizado como se fosse um identificador de execução. O leitor incremental usa `cursor` e `max_chars`.

**Recuperação:** `interrupt_incomplete_from_other_runtime` fornece um mecanismo explícito de tratamento de execuções de outro runtime. Não prometer retomada automática da execução de comandos arbitrários após crash; a recuperação do registro/resultado é distinta de reexecutar o comando.

## Contrato de leitura em lote

O código `app_rewrite/read_only_batch.py` aceita apenas `GIT_STATUS`, `GIT_HEAD`, `GIT_BRANCH`, `VERSION`, `FILE_STAT` e `SHA256`. Cada objeto permite `id`, `kind` e `path`. `VERSION` não aceita `path`; os outros exigem `path`. Há máximo de **32 operações** e **8 workers**, conforme a versão auditada. Falha de validação rejeita o lote.

```json
{
  "operations": [
    {"id": "status", "kind": "GIT_STATUS", "path": "C:\\Users\\Matheus\\CodeBridge-MCP-Bridge"},
    {"id": "version", "kind": "VERSION"}
  ]
}
```

Esta é a chamada de `codebridge_read_batch`, não `requests`. Embora seja somente leitura, verificações de arquivos podem retornar informações sensíveis de metadados; respeitar escopo e autorização.

## Proteções e limites

- Hashes e ledger ajudam na rastreabilidade; não constituem autorização de cada comando.
- O host Windows delimita os recursos reais disponíveis a cada processo.
- O tráfego MCP remoto depende do túnel/configuração segura; a API local não deve ser exposta indiscriminadamente.
- O índice RAG contém dados derivados das fontes. Políticas de exclusão e aprovação protegem a admissão, mas não substituem revisão da informação recuperada.
- Sistemas de atualização/rollback NSIS ainda não estão certificados para alterar a instalação ativa.

**Fontes do código:** `app_rewrite/config_store.py`, `credential_store.py`, `dpapi_secret_store.py`, `ipc_named_pipe.py`, `windows_control_channel.py`, `single_instance.py`, `execution_ledger.py`, `job_store.py`, `read_only_batch.py`, `author_mcp_manager.py`, `secure_tunnel_manager.py`.
