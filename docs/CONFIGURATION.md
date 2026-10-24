# Configuração operacional

## Windows e dependências

O CodeBridge usa Python/PySide6 no desktop e servidor MCP autoral. Versão de runtime, portas locais e capacidades devem ser verificadas na instância conectada. A branch de código não garante que o desktop já carregou alterações recentes.

## Terminal SSH

`ConfigStore.save_ssh(host, port)` armazena host/porta. `WindowsCredentialStore.save` protege usuário/senha no Windows Credential Manager. `TerminalManager.configure_ssh` registra configuração, `test_ssh` verifica a conexão e `ssh_settings` retorna os parâmetros não secretos. Um SSH configurado pode estar offline.

## Túnel seguro e organização

`ConfigStore.save_company` mantém metadados de empresa/túnel. `SecureTunnelManager.save_runtime_key` protege a chave pelo armazenamento DPAPI e `prepare_profile`, `start`, `status`, `stop` controlam o túnel. Não copiar API key em texto puro para scripts, mensagens ou documentos.

## Endereços

Em uma configuração observada, o MCP local serve `127.0.0.1:8765/mcp` e o adapter atende `127.0.0.1:8766`. São endereços de loopback. A configuração real pode mudar; não configurar firewall para expô-los diretamente em interfaces públicas.

## Preferências de interface

`ConfigStore` possui métodos para execução automática e notificação sonora. Alterações no aplicativo devem respeitar a opção atual, o foco dos terminais e as regras de execução segura.

## Verificação de funcionamento

1. Consultar `codebridge_status()` e observar `overall`, handshake e terminais.
2. Consultar `codebridge_capabilities()` para alvos e limites.
3. Para PowerShell, executar comando não destrutivo usando `codebridge_exec` e consultar `codebridge_wait` se necessário.
4. Consultar `codebridge_rag_status()` antes de pesquisar o conhecimento.
5. Confirmar SSH separadamente quando esse alvo for necessário.

Não considerar RAG pronto para escrita apenas porque seu estado de leitura está `READY`. Mais detalhes em [RAG.md](RAG.md) e [SECURITY.md](SECURITY.md).