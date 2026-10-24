# Segurança do CodeBridge

## Limites de confiança

O cliente MCP pode solicitar ações, mas a execução ocorre no computador autorizado com as permissões da conta efetiva. O túnel não deve publicar portas internas sem controle de autenticação. Entradas externas e respostas de pesquisa não são comandos confiáveis por padrão.

## Proteção de credenciais

- `app_rewrite/credential_store.py::WindowsCredentialStore` usa Windows Credential Manager para o login/senha SSH.
- `app_rewrite/dpapi_secret_store.py::DPAPISecretStore` protege a chave de runtime do túnel por DPAPI do Windows.
- `app_rewrite/config_store.py::ConfigStore` armazena preferências e configurações; não deve ser tratado como cofre criptográfico para todos os campos.

Não expor credenciais em commits, ferramentas MCP, screenshots, logs ou arquivos de documentação.

## Isolamento e IPC

`single_instance.py` usa mutex Windows. `ipc_named_pipe.py` implementa Named Pipes com tamanho máximo de frame, framing e ACL baseada no SID do usuário atual. `windows_control_channel.py` coordena o canal de controle. API e MCP locais usam loopback por padrão; o acesso externo autorizado ocorre pelo transporte configurado.

## Execução

Comandos PowerShell/CMD/SSH podem alterar ou excluir arquivos, instalar software e acessar recursos da conta. Confirmar alvos, parâmetros e efeitos antes de ações irreversíveis. `request_id`, `execution_id` e ledger ajudam no rastreio; não substituem autorização.

## Fontes do RAG

`rag/sources/exclusion_policy.py` rejeita diretórios de cache, dependências, builds, backups, binários, extensões de chaves, credenciais e arquivos temporários. `secret_detection.py` acrescenta avaliação de conteúdo sensível. Prévia de indexação não é permissão permanente para publicar fontes.

## Política de falha segura

Não contornar bloqueios de publicação RAG, integridade de geração ou atualização instalada. Uma falha de pré-condição deve impedir a ação, não ser transformada em sucesso presumido. Para procedimentos de recuperação consulte [RECOVERY.md](RECOVERY.md).