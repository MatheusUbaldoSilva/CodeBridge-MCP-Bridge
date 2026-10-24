# Armazenamento e persistência

## Configurações e preferências

`app_rewrite/config_store.py::ConfigStore` lê/grava o arquivo JSON de configuração local. Abrange host/porta SSH, preferências de execução e som, e dados não secretos de conexão da empresa. O processo utiliza escrita por substituição para reduzir risco de arquivo parcial.

Credenciais SSH ficam no Windows Credential Manager via `WindowsCredentialStore`; segredo do túnel é protegido em blob DPAPI pelo `DPAPISecretStore`. Esses stores não devem ser confundidos com o arquivo de configuração.

## Execuções e jobs

| Implementação | Informação persistida |
|---|---|
| `app_rewrite/execution_ledger.py::ExecutionLedger` | IDs, estados, hash do comando, timestamps e saída de execução |
| `app_rewrite/job_store.py::JobStore` | jobs, aprovação, preparação, execução, finalização e contadores |
| `app_rewrite/external_prepare_store.py` | identidade e estado das preparações externas |
| `app_rewrite/external_execute_store.py` | identidade e estado dos pedidos externos de execução |

O ledger usa SQLite com transações e operações `create`, `transition`, `append_output`, `read_output` e interrupção de execuções incompletas de outro runtime. Estados finais não devem ser alterados como se fossem pendentes.

## Índice RAG

O armazenamento local inclui geração selecionada pelo ponteiro `active-generation.json`, manifesto, SQLite FTS5 e artefatos Qdrant. Os metadados de documentos/chunks podem incluir path, hash, linhas e Git. O diretório efetivo é informado por `codebridge_rag_status`, podendo estar sob `%LOCALAPPDATA%\CodeBridge\rag`.

## Integridade e backups

Preservar os três componentes de uma geração (SQLite, Qdrant e manifesto), seu ponteiro e o estado de transição. Uma cópia parcial não é uma geração recuperável. Identificar artefatos por geração e conferir hash/manifesto antes de uma restauração.

## Restrições

Não colocar índices, chaves e credenciais no Git. Os dados da instalação ativa podem diferir dos artefatos gerados pela branch de código. Consulte [RECOVERY.md](RECOVERY.md) para transações e recuperação, e [SECURITY.md](SECURITY.md) para a classificação de segredos.