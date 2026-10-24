# Operação, implantação e recuperação — estado atual

Documento técnico do código existente na branch `rag-017-optimized-inference-after-candidate`. Reúne interfaces de operação e comportamentos implementados; **não** afirma que um mecanismo isolado esteja certificado para atualização de produção.

## Processo e serviços

| Componente | Contrato |
|---|---|
| `app_rewrite/runtime.py` | Runtime, ciclo de execução e coordenação dos componentes |
| `app_rewrite/api_server.py` | Adapter de API local autenticada |
| `app_rewrite/author_mcp_manager.py::AuthorMCPManager` | Inicia, consulta e encerra processos MCP próprios |
| `app_rewrite/secure_tunnel_manager.py::SecureTunnelManager` | Configura e supervisiona túnel seguro |
| `author_mcp/mcp_server.py` | API MCP Streamable HTTP e ferramentas expostas |
| `app_rewrite/terminal_manager.py::TerminalManager` | Autoridade única de sessões PowerShell, CMD e SSH |

No perfil observado: servidor MCP em `127.0.0.1:8765/mcp`, adapter em `127.0.0.1:8766`, túnel para o canal `main`. Endereços locais são **loopback**, não interfaces destinadas à exposição pública.

## Procedimento de diagnóstico sem alterar estado

1. `codebridge_status({})`: confirmar handshake, versão, `overall`, presença do adapter e `terminals`.
2. `codebridge_capabilities({})`: listar `targets`, `features`, `limits` e `preferred_tools`.
3. `codebridge_rag_status({})`: confirmar integridade básica e geração RAG apontada no status.
4. Opcional: `codebridge_read_batch({"operations":[...]})` para consultas Git, versão e metadados sem iniciar terminal de comando.
5. Só depois executar uma operação não destrutiva com `codebridge_exec`. Se a resposta estiver `RUNNING`, consultar `codebridge_wait` com o mesmo `execution_id`.

É incorreto tratar `overall=READY` como prova de que SSH está conectado ou que a publicação incremental do RAG está habilitada.

## Build NSIS conforme o script atual

`installer/build_installer.ps1` declara o parâmetro `[switch]$InstallNSIS`; o gerador é **NSIS/makensis**, não Inno Setup. O script lê `version.json`, prepara definições para `installer/CodeBridge.nsi`, gera `installer/dist/CodeBridge-Setup.exe`, calcula SHA-256 e gera o hash ao lado do artefato. Também copia o executável para a Área de Trabalho.

```powershell
.\installer\build_installer.ps1 -InstallNSIS
```

O parâmetro acima permite instalar/obter NSIS quando não encontrado de acordo com o fluxo do script; para ambientes controlados, revisar dependências, origem da ferramenta e efeitos antes de executar. O comando de build **não é** uma instrução para executar um cutover automaticamente.

O `installer/CodeBridge.nsi` especifica nome e versão, arquivos empacotados, páginas/guias de instalação/atualização, caminhos de destino, entradas HKCU de instalação/desinstalação e ícones. A presença desses recursos no script não equivale a validação de instalação em outra máquina.

## Instalação, configuração e armazenamento

- O aplicativo utiliza runtime Python isolado na instalação Windows.
- `app_rewrite/config_store.py` armazena configurações de usuário e empresa.
- `WindowsCredentialStore` protege o segredo SSH via Windows Credential Manager.
- `DPAPISecretStore` protege o segredo do runtime do túnel usando DPAPI no Windows.
- O estado dos terminais e as execuções podem depender do ledger e stores SQLite persistentes.
- O RAG instalado mantém os artefatos de geração em `%LOCALAPPDATA%\CodeBridge\rag`, conforme status.

**Não** copiar arquivos de credenciais em texto simples para pacotes de instalação, logs ou repositório.

## Recuperação do executor

`ExecutionLedger` registra estados e conteúdo de saída e oferece `interrupt_incomplete_from_other_runtime`. `TerminalManager` oferece métodos de cancelamento, reciclagem e recuperação de estado órfão. A recuperação de estado **não deve reexecutar um comando perigoso automaticamente**. Para uma operação sem resposta, primeiro recuperar por `execution_id` e analisar o estado.

O fechamento normal do aplicativo pode encerrar os processos MCP/túnel que ele iniciou. Nunca encerrar indiscriminadamente todos os processos `python.exe` do computador para realizar manutenção.

## Gerações RAG e recuperação

A base possui módulos de lock, lease, journal, cópia verificada, troca de ponteiro e leitura por geração em `rag/runtime/`. Há também preparação de candidato incremental, fila, worker offline e gates de scheduler.

- Um índice público já existente bloqueia o método de publicação inicial `production_publish.publish_staged_index`.
- A existência de um worker e de testes de rollback não significa que o scheduler/NSIS esteja liberado.
- Durante manutenção, preservar `active-generation.json`, SQLite, Qdrant, manifesto e os artefatos necessários à recuperação.
- Não substituir o índice ativo por uma simples cópia de diretórios sem validação do ponteiro, locks e consistência.

## Status de liberação

| Recurso | Condição atual |
|---|---|
| Terminal PowerShell/CMD pelo MCP | Operacional na instalação observada |
| SSH | Implementado, sujeito a conexão |
| Consulta ao índice RAG ativo | Operacional na geração observada |
| Prévia RAG de pastas/arquivos | Implementada na interface |
| Escrita incremental/publicação de novas fontes | Bloqueada ou não certificada |
| Transação completa NSIS com recuperação supervisionada P9-B | Não certificada para cutover da instalação em produção |

## Continuidade por checkpoint MCP

As ferramentas `codebridge_dev_checkpoint_save` e `codebridge_dev_checkpoint_latest` estão registradas em `author_mcp/development_checkpoint_tools.py`. Elas gravam/consultam resumos operacionais associados à sessão ativa, mas não substituem Git, backup, transações nem recuperação de processo.

## Regras de manutenção

- Fixar a revisão Git e preservar alterações locais não commitadas antes de atualização.
- Usar `git diff --check`, testes focados e auditoria pós-commit; não afirmar aprovação dos testes não executados.
- Testar procedimentos destrutivos/rollback em ambiente isolado antes de aplicá-los à máquina instalada.
- Fazer alterações de configuração e credenciais apenas pelos mecanismos previstos.
- Diferenciar o estado **do código** do estado **do aplicativo instalado** e do estado **da conexão MCP**.

**Fontes:** `installer/build_installer.ps1`, `installer/CodeBridge.nsi`, `app_rewrite/runtime.py`, `api_server.py`, `author_mcp_manager.py`, `secure_tunnel_manager.py`, `terminal_manager.py`, `execution_ledger.py`, `config_store.py`, `credential_store.py`, `dpapi_secret_store.py`, `rag/runtime/`.

## Testes contra a fonte local

Quando o Python isolado instalado é utilizado, seu `sys.path` pode preferir módulos da instalação em vez dos módulos da branch. Para executar a suíte contra o checkout, use `tests/run_repo_tests.py`, que posiciona a raiz do repositório primeiro e verifica a origem do pacote `installer`.

```powershell
$py = Join-Path $env:LOCALAPPDATA 'Programs\CodeBridge\runtime\python\python.exe'
& $py tests\run_repo_tests.py test_installer_runtime_fingerprints.py test_rag_p9b_installer_rollback_scope.py
```

A fixture de baseline pública usada nos testes de integridade está em `tests/fixtures/rag_public_index_baseline_fixture.json`. Esse arquivo é material de teste; não deve ser confundido com a geração pública ativa.

## Restrições atuais à retirada de documentos

A suíte de 100 consultas `benchmarks/rag014_ground_truth.jsonl` contém 26 caminhos de documentos antigos utilizados por 32 consultas; esses caminhos ainda precisam de um corpus de avaliação apropriado antes de sua retirada. A geração RAG observada mantém 108 documentos antigos da pasta `docs/` e nenhum dos novos documentos principais. A exclusão desses arquivos não deve ocorrer antes de validar uma nova geração, sem modificar diretamente os artefatos ativos.
