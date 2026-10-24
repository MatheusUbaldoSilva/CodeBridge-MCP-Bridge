# Instalação e atualização Windows

## Componentes do pacote

O instalador é definido em `installer/CodeBridge.nsi` (NSIS). O build é preparado por `installer/build_installer.ps1`, que usa `version.json`, verifica a disponibilidade de `makensis` e gera o executável `installer/dist/CodeBridge-Setup.exe` e hash SHA-256.

## Compilação

```powershell
.\installer\build_installer.ps1 -InstallNSIS
```

O switch `-InstallNSIS` habilita o fluxo previsto pelo script para disponibilizar o compilador quando necessário. Revise permissões e origem das dependências antes de executar.

## Arquivos empacotados

O script NSIS inclui runtime/app Python, servidor MCP/adapter, módulos RAG, assets, ferramentas auxiliares e documentação de instalação. O arquivo exato incluso em `docs/` é `INSTALLATION.md`. O pacote cria atalhos, registra instalação/desinstalação em HKCU e pode executar bootstrap; operações efetivas dependem da revisão do script.

## Instalação existente

O aplicativo mantém configurações e segredos do usuário por stores próprios. Antes de atualizar, conferir versão instalada, hash do instalador, estado do runtime, caminhos de destino e dados preservados. O build de um novo instalador não significa que sua aplicação imediata esteja segura.

## Limite atual de lançamento

O repositório possui mecanismos de preflight, snapshot e rollback em `installer/`, mas **não existe certificação de cutover transacional para a instalação de produção** nesta documentação. Não acionar atualizador ou parada real do MCP apenas para validar o pacote.

## Verificação após instalação

Confirmar: interface abre, versão exibida, `codebridge_status` e `codebridge_capabilities` respondem, terminais locais conectam, túnel autorizado tem handshake, SSH é opcional e `codebridge_rag_status` consulta a geração esperada. Falha de um desses itens não pode ser mascarada por instalador com exit code zero.

Para configurar conexão consulte [CONFIGURATION.md](CONFIGURATION.md); para segurança e rollback consulte [RECOVERY.md](RECOVERY.md).