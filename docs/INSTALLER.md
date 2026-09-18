# Instalador do CodeBridge

O `CodeBridge-Setup.exe` instala o CodeBridge em um computador Windows sem exigir Python, Git ou preparação manual.


## Usar o instalador pronto

O executável pronto fica em:

`installer\dist\CodeBridge-Setup.exe`

Fluxo no computador da empresa:

1. execute `CodeBridge-Setup.exe`;
2. aguarde a instalação automática do runtime e das dependências;
3. no assistente, abra a página de API Keys da organização e crie a chave da empresa;
4. abra a página de Tunnels e crie um tunnel para aquele computador;
5. cole a API key e o `Tunnel ID` no assistente;
6. siga a tela **Criar o MCP no ChatGPT**;
7. finalize e teste `codebridge_ping` pelo ChatGPT.

A instalação é por usuário em `%LOCALAPPDATA%\Programs\CodeBridge`, evitando depender de Python ou Git instalados no computador.

## O que o instalador faz

- instala os arquivos do CodeBridge em `C:\\Program Files\\CodeBridge`;
- baixa um runtime Python 3.13 isolado dentro da própria instalação;
- instala automaticamente as dependências Python do aplicativo e do MCP autoral;
- instala `tunnel-client.exe` e `cloudflared.exe` usados pelo OpenAI Tunnel;
- cria atalhos no Menu Iniciar e na Área de Trabalho;
- abre o assistente de configuração empresarial;
- solicita a API key da organização;
- solicita o Tunnel ID criado para o computador;
- protege a API key localmente com Windows DPAPI;
- gera o perfil do tunnel-client;
- ensina a criar o plugin/MCP no ChatGPT;
- permite executar o teste final `codebridge_ping`.

## Requisitos do computador cliente

- Windows 10/11 x64;
- conexão com a internet durante a instalação;
- permissão de administrador para instalar em Program Files;
- acesso à organização da empresa na OpenAI Platform;
- conta do ChatGPT que possa criar/configurar Plugins.

O instalador é atualmente **não assinado**. O Windows SmartScreen pode exibir um aviso até que o executável seja assinado com um certificado de code signing.

## Configuração guiada

### 1. Criar API key da organização

Abra:

https://platform.openai.com/settings/organization/api-keys

Crie uma chave apropriada para a empresa e copie o valor. O assistente solicita essa chave e a grava usando DPAPI.

Para computador de empresa, prefira uma **Conta de serviço**. Para validação inicial, uma chave vinculada ao usuário também funciona, desde que tenha as permissões corretas.

Se a chave estiver como **Restrito**, a permissão **Túneis** não pode ficar em **Nenhum**. Para executar o `tunnel-client`, a identidade precisa de **Ler + Usar** em Túneis. Para criar ou editar túneis pela Plataforma, também é necessária a permissão de gerenciamento apropriada no nível da organização.

A chave **não é salva no repositório, no README ou em texto puro**.

### 2. Criar o OpenAI Tunnel

Abra:

https://platform.openai.com/settings/organization/tunnels

Crie um túnel para o computador que está sendo configurado e copie o `Tunnel ID`, normalmente no formato `tunnel_...`.

O CodeBridge cria um perfil local específico para esse Tunnel ID e aponta o canal MCP para:

`http://127.0.0.1:8765/mcp`

### 3. Criar o MCP no ChatGPT

No ChatGPT:

1. abra **Configurações > Plugins > Novo plugin**;
2. use o logo `assets/codebridge_plugin_256.png`;
3. use o nome sugerido pelo assistente, por padrão **CodeBridge MCP**;
4. em **Conexão**, selecione o OpenAI Tunnel criado para esse computador;
5. não reutilize a API key da organização como senha do plugin: ela é usada localmente pelo `tunnel-client`;
6. salve o plugin.

### 4. Teste final

Com o CodeBridge aberto, no ChatGPT envie:

`Use o CodeBridge e chame codebridge_ping com desafio TESTE_INSTALACAO.`

O retorno deve confirmar o handshake do CodeBridge.

## Configurar novamente

O instalador cria no Menu Iniciar:

**CodeBridge > Configurar CodeBridge**

Esse atalho reabre o assistente para trocar empresa, nome do plugin, API key e Tunnel ID.

Se o Tunnel ID mudar, um novo perfil do tunnel-client é criado automaticamente.

## Dados locais

Configurações não secretas:

`%LOCALAPPDATA%\\CodeBridge-MCP-Bridge\\config.json`

API key protegida por DPAPI:

`%LOCALAPPDATA%\\CodeBridge-MCP-Bridge\\secure_tunnel_runtime_key.dpapi`

Perfil do tunnel-client:

`%APPDATA%\\tunnel-client\\codebridge-*.yaml`

Logs:

`%LOCALAPPDATA%\\CodeBridge-MCP-Bridge\\installer.log`

## Build do instalador

No computador de desenvolvimento:

```powershell
cd C:\\Users\\Matheus\\CodeBridge-MCP-Bridge
.\\installer\\build_installer.ps1 -InstallInno
```

O script verifica os binários do tunnel client, instala o NSIS via winget se necessário, compila o instalador, gera `installer\\dist\\CodeBridge-Setup.exe`, copia o executável para a Área de Trabalho e mostra o SHA-256.

## Atualização

O mesmo `CodeBridge-Setup.exe` pode ser executado novamente sobre a instalação existente. Os dados do usuário em `%LOCALAPPDATA%` e `%APPDATA%` não são apagados pelo instalador.

## Segurança

- a API key não é embutida no instalador;
- cada cliente informa a própria API key e o próprio Tunnel ID;
- a API key é protegida com DPAPI no perfil do Windows que executa a configuração;
- o túnel aponta apenas para o MCP local do CodeBridge;
- credenciais SSH continuam no Windows Credential Manager;
- o instalador não inclui as credenciais SSH do computador usado para compilar.
